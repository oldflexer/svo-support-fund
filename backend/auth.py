import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app
from models import AdminUser, AuditLog, db

class AuthError(Exception):
    """Исключение для ошибок аутентификации"""
    pass

def create_access_token(user_id, username, role):
    """Создание JWT токена"""
    try:
        payload = {
            'exp': datetime.datetime.utcnow() + current_app.config['JWT_ACCESS_TOKEN_EXPIRES'],
            'iat': datetime.datetime.utcnow(),
            'sub': user_id,
            'username': username,
            'role': role,
            'type': 'access'
        }
        return jwt.encode(
            payload,
            current_app.config['JWT_SECRET_KEY'],
            algorithm='HS256'
        )
    except Exception as e:
        raise AuthError(f"Error creating token: {str(e)}")

def create_refresh_token(user_id):
    """Создание refresh токена"""
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
    """Верификация JWT токена с возможной проверкой 2FA"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['JWT_SECRET_KEY'],
            algorithms=['HS256']
        )
        
        # Если требуется 2FA, проверяем что она пройдена
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
    """Извлечение токена из заголовка Authorization"""
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        raise AuthError('Authorization header is missing')
    
    parts = auth_header.split()
    if len(parts) != 2 or parts[0] != 'Bearer':
        raise AuthError('Authorization header must be Bearer token')
    
    return parts[1]

def login_required(func, require_2fa=False):
    """
    Декоратор для защиты маршрутов, требующих аутентификации
    
    Args:
        require_2fa: Требовать ли проверку 2FA
    """
    def decorator(*args, **kwargs):
        try:
            token = get_token_from_header()
            payload = verify_token(token)
            
            # Проверяем, что токен access, а не refresh
            if payload.get('type') != 'access':
                raise AuthError('Invalid token type')
            
            # Получаем пользователя из базы
            user = AdminUser.query.get(payload['sub'])
            if not user or not user.is_active:
                raise AuthError('User not found or inactive')
            
            # Если требуется 2FA, проверяем что она пройдена
            if require_2fa and user.two_factor_enabled:
                if not payload.get('2fa_verified', False):
                    raise AuthError('2FA verification required')
            
            # Добавляем пользователя в контекст запроса
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
    """Создание JWT токена с учётом 2FA"""
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
    """Декоратор для проверки ролей пользователя"""
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
    """Логирование действий администратора"""
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
    """Валидация пароля"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    return True, "Password is valid"