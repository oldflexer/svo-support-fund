import jwt
import datetime
from flask import request, jsonify, current_app
from models import AdminUser, AuditLog, db

class AuthError(Exception):
    """Exception for authentication errors"""
    pass

def create_refresh_token(user_id):
    """Create refresh token"""
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + current_app.config['JWT_REFRESH_TOKEN_EXPIRES'],
            'iat': datetime.datetime.utcnow(),
            'sub': user_id,
            'type': 'refresh'
        }
        return jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
    except Exception as e:
        raise AuthError(f"Error creating refresh token: {str(e)}")

def verify_token(token, require_2fa=False):
    """Verify JWT token with optional 2FA check"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        
        # If 2FA is required, check that it has been completed
        if require_2fa:
            user = AdminUser.query.get(payload['sub'])
            if user and user.two_factor_enabled and not payload.get('2fa_verified', False):
                raise AuthError('2FA verification required')
        
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthError('Token has expired')
    except jwt.InvalidTokenError:
        raise AuthError('Invalid token')

def get_token_from_header():
    """Extract token from Authorization header"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise AuthError('Authorization header is missing')
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != 'Bearer':
        raise AuthError('Authorization header must be Bearer token')
    
    return parts[1]

def login_required(func, require_2fa=False):
    """
    Decorator for protecting routes that require authentication
    Args:
        require_2fa: Whether to require 2FA verification
    """
    def decorator(*args, **kwargs):
        try:
            token = get_token_from_header()
            payload = verify_token(token)
            
            # Check that the token is access, not refresh
            if payload.get('type') != 'access':
                raise AuthError('Invalid token type')
            
            # Get user from database
            user = AdminUser.query.get(payload['sub'])
            if not user or not user.is_active:
                raise AuthError('User not found or inactive')
            
            # If 2FA is required, check that it has been completed
            if require_2fa and user.two_factor_enabled:
                if not payload.get('2fa_verified', False):
                    raise AuthError('2FA verification required')
            
            # Add user to request context
            request.current_user = user
            return func(*args, **kwargs)
        
        except AuthError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 401
        
    decorator.__name__ = func.__name__
    return decorator
    
def create_access_token(user_id, username, role, two_factor_verified=False):
    """Create JWT token with 2FA consideration"""
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
            'iat': datetime.datetime.utcnow(),
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
        raise AuthError(f"Error creating token: {str(e)}")

def role_required(*roles):
    """Decorator for checking user roles"""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if request.current_user.role not in roles:
                return jsonify({
                    'success': False,
                    'message': 'Insufficient permissions'
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

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

def validate_password(password):
    """Validate password"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    return True, "Password is valid"