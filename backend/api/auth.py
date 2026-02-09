"""
Authentication API endpoints
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from datetime import datetime, timedelta
import jwt
import pyotp
import json

from models import db, AdminUser, FailedLoginAttempt, AuditLog
from schemas import validate_request, SCHEMAS
from utils.helpers import format_date, format_currency

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/api/auth/login', methods=['POST'])
@cross_origin()
def login():
    """User login with JWT and 2FA support"""
    try:
        # Validate login data
        data = validate_request('login', request.json)
        
        # Find user by username or email
        user = AdminUser.query.filter(
            (AdminUser.username == data['username']) |
            (AdminUser.email == data['username'])
        ).first()
        
        if not user:
            # Record failed attempt
            record_failed_attempt(data['username'], reason='user_not_found')
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
        
        if not user.is_active:
            record_failed_attempt(data['username'], reason='account_inactive')
            return jsonify({
                'success': False,
                'message': 'Account is inactive'
            }), 401
        
        # Check password
        if not user.check_password(data['password']):
            record_failed_attempt(data['username'], reason='wrong_password')
            return jsonify({
                'success': False,
                'message': 'Invalid username or password'
            }), 401
        
        # Check rate limiting
        allowed, wait_time = check_rate_limit(data['username'], request.remote_addr)
        if not allowed:
            return jsonify({
                'success': False,
                'message': 'Too many login attempts',
                'wait_time': wait_time
            }), 429
        
        # Clear previous failed attempts
        clear_failed_attempts(data['username'])
        
        # If 2FA is enabled, return temp token for verification
        if user.two_factor_enabled:
            temp_token = generate_temp_token(user.id, data['username'])
            
            # Log audit
            log_audit('login_attempt', 'user', user.id, '2FA required')
            
            return jsonify({
                'success': True,
                'message': 'Two-factor authentication required',
                'two_factor_required': True,
                'temp_token': temp_token,
                'username': data['username']
            })
        
        # Generate tokens
        access_token = create_access_token(user.id, user.username, user.role)
        refresh_token = create_refresh_token(user.id)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log audit
        log_audit('login', 'user', user.id, 'Successful login')
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict_without_secrets(),
            'two_factor_required': user.two_factor_enabled
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login error: {str(e)}'
        }), 500


@auth_bp.route('/api/auth/2fa/verify', methods=['POST'])
@cross_origin()
def verify_two_factor():
    """Verify 2FA token"""
    try:
        # Validate data
        data = validate_request('two_factor_verify', request.json)
        
        # Decode temp token
        temp_token_data = decode_temp_token(data['temp_token'])
        if not temp_token_data:
            return jsonify({
                'success': False,
                'message': 'Invalid temp token'
            }), 400
        
        # Find user
        user = AdminUser.query.get(temp_token_data['user_id'])
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found'
            }), 404
        
        # Verify 2FA token
        if not user.verify_two_factor_token(data['two_factor_token']) and not user.verify_backup_code(data['two_factor_token']):
            record_failed_attempt(temp_token_data['username'], user.id, reason='2fa_failed')
            return jsonify({
                'success': False,
                'message': 'Invalid 2FA token'
            }), 401
        
        # Generate tokens with 2FA verification flag
        access_token = create_access_token(
            user.id, user.username, user.role, 
            two_factor_verified=True
        )
        refresh_token = create_refresh_token(user.id)
        
        # Update last login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Log audit
        log_audit('login', 'user', user.id, 'Successful login with 2FA')
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict_without_secrets(),
            'two_factor_required': user.two_factor_enabled
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'2FA verification error: {str(e)}'
        }), 500


@auth_bp.route('/api/auth/refresh', methods=['POST'])
@cross_origin()
def refresh_token():
    """Refresh access token"""
    try:
        # Validate data
        data = validate_request('refresh_token', request.json)
        
        # Decode refresh token
        try:
            payload = jwt.decode(
                data['refresh_token'],
                current_app.config['JWT_SECRET_KEY'],
                algorithms=['HS256']
            )
            
            if payload.get('type') != 'refresh':
                raise jwt.InvalidTokenError()
                
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'message': 'Refresh token has expired'
            }), 401
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Invalid refresh token'
            }), 401
        
        # Find user
        user = AdminUser.query.get(payload['sub'])
        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'message': 'User not found or inactive'
            }), 404
        
        # Generate new access token
        access_token = create_access_token(
            user.id, user.username, user.role,
            two_factor_verified=payload.get('2fa_verified', False)
        )
        
        return jsonify({
            'success': True,
            'access_token': access_token
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Token refresh error: {str(e)}'
        }), 500


@auth_bp.route('/api/auth/logout', methods=['POST'])
@cross_origin()
def logout():
    """User logout"""
    try:
        # Log audit
        if hasattr(request, 'current_user'):
            log_audit('logout', 'user', request.current_user.id, 'User logged out')
        
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Logout error: {str(e)}'
        }), 500


@auth_bp.route('/api/auth/me', methods=['GET'])
@cross_origin()
@login_required
def get_current_user():
    """Get current user information"""
    try:
        user = request.current_user
        
        return jsonify({
            'success': True,
            'data': user.to_dict_without_secrets()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting user info: {str(e)}'
        }), 500


def create_access_token(user_id, username, role, two_factor_verified=False):
    """Create JWT access token"""
    try:
        payload = {
            'exp': datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
            'iat': datetime.utcnow(),
            'sub': user_id,
            'username': username,
            'role': role,
            'type': 'access',
            '2fa_verified': two_factor_verified,
            '2fa_required': AdminUser.query.get(user_id).two_factor_enabled if AdminUser.query.get(user_id) else False
        }
        return jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
    except Exception as e:
        raise Exception(f'Error creating access token: {str(e)}')


def create_refresh_token(user_id):
    """Create JWT refresh token"""
    try:
        payload = {
            'exp': datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES'],
            'iat': datetime.utcnow(),
            'sub': user_id,
            'type': 'refresh'
        }
        return jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
    except Exception as e:
        raise Exception(f'Error creating refresh token: {str(e)}')


def generate_temp_token(user_id, username):
    """Generate temporary token for 2FA verification"""
    try:
        payload = {
            'exp': datetime.utcnow() + timedelta(minutes=5),
            'iat': datetime.utcnow(),
            'sub': user_id,
            'username': username,
            'type': 'temp_2fa'
        }
        return jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
    except Exception as e:
        raise Exception(f'Error generating temp token: {str(e)}')


def decode_temp_token(temp_token):
    """Decode temporary 2FA token"""
    try:
        payload = jwt.decode(
            temp_token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        
        if payload.get('type') != 'temp_2fa':
            return None
            
        return payload
        
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def check_rate_limit(username, ip_address):
    """Check login rate limit"""
    # Limit: maximum 5 attempts per 15 minutes
    time_threshold = datetime.utcnow() - timedelta(minutes=15)
    
    # Count attempts by IP
    ip_attempts = FailedLoginAttempt.query.filter(
        FailedLoginAttempt.ip_address == ip_address,
        FailedLoginAttempt.attempted_at >= time_threshold
    ).count()
    
    # Count attempts by username
    user_attempts = FailedLoginAttempt.query.filter(
        FailedLoginAttempt.username == username,
        FailedLoginAttempt.attempted_at >= time_threshold
    ).count()
    
    max_attempts = 5
    
    if ip_attempts >= max_attempts or user_attempts >= max_attempts:
        # Find oldest attempt within window
        oldest_attempt = FailedLoginAttempt.query.filter(
            FailedLoginAttempt.ip_address == ip_address,
            FailedLoginAttempt.attempted_at >= time_threshold
        ).order_by(FailedLoginAttempt.attempted_at).first()
        
        if oldest_attempt:
            wait_until = oldest_attempt.attempted_at + timedelta(minutes=15)
            wait_seconds = (wait_until - datetime.utcnow()).total_seconds()
            return False, max(0, int(wait_seconds))
    
    return True, 0


def record_failed_attempt(username, admin_id=None, reason='wrong_password'):
    """Record failed login attempt"""
    attempt = FailedLoginAttempt(
        username=username,
        admin_id=admin_id,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
        reason=reason
    )
    
    db.session.add(attempt)
    db.session.commit()


def clear_failed_attempts(username):
    """Clear failed login attempts after successful login"""
    FailedLoginAttempt.query.filter_by(username=username).delete()
    db.session.commit()


def log_audit(action, entity_type=None, entity_id=None, details=None):
    """Log admin actions"""
    if hasattr(request, 'current_user'):
        audit_log = AuditLog(
            admin_id=request.current_user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string
        )
        db.session.add(audit_log)
        db.session.commit()