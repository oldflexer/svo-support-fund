"""
Middleware functions for authentication and authorization
"""

from functools import wraps
from flask import request, jsonify, current_app
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
import jwt
import bcrypt
import pyotp
import re

from backend.models import AdminUser, TwoFactor
from backend.config import Config

# Authentication middleware

def login_required(f):
    """Decorator to require login for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check for Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return jsonify({'success': False, 'message': 'Authorization header is missing or malformed'}), 401
            
            token = auth_header.split()[1]
            
            # Verify token
            try:
                payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
                
                # Check if user exists and is active
                user = AdminUser.query.get(payload['user_id'])
                if not user or not user.is_active:
                    return jsonify({'success': False, 'message': 'Invalid or inactive user'}), 401
                
                # Check if token is expired
                if datetime.utcnow() > datetime.utcfromtimestamp(payload['exp']):
                    return jsonify({'success': False, 'message': 'Token has expired'}), 401
                
                # Store current user in app config for later use
                current_app.config['current_user_id'] = user.id
                current_app.config['current_user_role'] = user.role
                
            except jwt.ExpiredSignatureError:
                return jsonify({'success': False, 'message': 'Token has expired'}), 401
            except jwt.InvalidTokenError:
                return jsonify({'success': False, 'message': 'Invalid token'}), 401
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Authentication error: {str(e)}'}), 401
    
    return decorated_function

# Authorization middleware

def admin_required(f):
    """Decorator to require admin role for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check if user has admin role
            user_role = current_app.config.get('current_user_role')
            if not user_role or user_role != 'admin':
                return jsonify({'success': False, 'message': 'Admin access required'}), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'Authorization error: {str(e)}'}), 403
    
    return decorated_function

# 2FA middleware

def two_factor_required(f):
    """Decorator to require 2FA for protected routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            # Check if user has 2FA enabled
            user_id = current_app.config.get('current_user_id')
            if not user_id:
                return jsonify({'success': False, 'message': 'User not authenticated'}), 401
            
            user = AdminUser.query.get(user_id)
            if not user or not user.two_factor_enabled:
                return jsonify({'success': False, 'message': '2FA is required for this account'}), 403
            
            # Check for 2FA token in headers
            two_factor_header = request.headers.get('X-2FA-Token')
            if not two_factor_header:
                return jsonify({'success': False, 'message': '2FA token is required'}), 403
            
            # Verify 2FA token
            two_factor = TwoFactor.query.filter_by(admin_id=user_id).first()
            if not two_factor:
                return jsonify({'success': False, 'message': '2FA not configured'}), 403
            
            totp = pyotp.TOTP(two_factor.secret)
            if not totp.verify(two_factor_header):
                return jsonify({'success': False, 'message': 'Invalid 2FA token'}), 403
            
            return f(*args, **kwargs)
            
        except Exception as e:
            return jsonify({'success': False, 'message': f'2FA error: {str(e)}'}), 403
    
    return decorated_function

# Rate limiting middleware

def rate_limit(limit, per):
    """Decorator to limit request rate"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get client IP
            client_ip = request.remote_addr
            
            # Track requests in memory (in production, use Redis or database)
            if not hasattr(decorated_function, '_request_count'):
                decorated_function._request_count = {}
            
            current_time = datetime.utcnow()
            key = f"{client_ip}_{f.__name__}"
            
            # Clean old requests
            if key in decorated_function._request_count:
                decorated_function._request_count[key] = [
                    (time, count) for time, count in decorated_function._request_count[key]
                    if current_time - time < timedelta(seconds=per)
                ]
            
            # Count current requests
            current_count = sum(count for time, count in decorated_function._request_count.get(key, []) if current_time - time < timedelta(seconds=per))
            
            if current_count >= limit:
                return jsonify({
                    'success': False,
                    'message': f'Rate limit exceeded. Try again in {per} seconds.'
                }), 429
            
            # Add current request
            if key not in decorated_function._request_count:
                decorated_function._request_count[key] = []
            
            # Find existing entry for current second
            found = False
            for i, (time, count) in enumerate(decorated_function._request_count[key]):
                if (current_time - time).total_seconds() < 1:
                    decorated_function._request_count[key][i] = (time, count + 1)
                    found = True
                    break
            
            if not found:
                decorated_function._request_count[key].append((current_time, 1))
            
            return f(*args, **kwargs)
        
        return decorated_function
    
    return decorator

# Input validation middleware

def validate_input(schema):
    """Decorator to validate request input using marshmallow schema"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                data = request.get_json() or {}
                errors = schema.validate(data)
                
                if errors:
                    return jsonify({
                        'success': False,
                        'message': 'Validation error',
                        'errors': errors
                    }), 400
                
                return f(*args, **kwargs)
                
            except Exception as e:
                return jsonify({
                    'success': False,
                    'message': f'Validation error: {str(e)}'
                }), 400
        
        return decorated_function
    
    return decorator
