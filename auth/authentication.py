"""
Authentication blueprint.

This module provides endpoints for user authentication including login, logout,
token refresh, and retrieval of current user information. It handles standard
password login and two-factor authentication (2FA) flow.
"""

from datetime import datetime, UTC
from flask import request, jsonify
from flask_jwt_extended import jwt_required, create_access_token, create_refresh_token
from models import db, User
from utils import get_jwt_identity, log_action
from . import auth_bp

# -------------------------------
# API: Authentication
# -------------------------------

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Authenticate a user and issue access/refresh tokens.
    Expects JSON with 'username' and 'password'.
    If 2FA is enabled, returns a temporary token and requires a second step.
    Otherwise returns access and refresh tokens with user data.
    """
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Учетная запись деактивирована'}), 403
    
    # Check 2FA
    if user.two_factor_enabled:
        # Return a flag that 2FA is required
        temp_token = create_access_token(identity=user.id, additional_claims={'requires_2fa': True}, expires_delta=False)
        return jsonify({
            'requires_2fa': True,
            'temp_token': temp_token,
            'username': user.username
        }), 200
    
    # No 2FA, full login
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    user.last_login = datetime.now(UTC)
    db.session.commit()
    
    log_action(user.id, 'login', 'Успешный вход', request.remote_addr)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """
    Log out the current user.
    Requires a valid access token. Logs the action and returns a success message.
    """
    log_action(get_jwt_identity(), 'logout', 'Выход успешно выполнен', request.remote_addr)
    return jsonify({'message': 'Выход выполнен'}), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh an expired access token using a valid refresh token.
    Returns a new access token.
    """
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    log_action(get_jwt_identity(), 'refresh', 'Успешно обновлен токен', request.remote_addr)
    return jsonify({'access_token': access_token}), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Retrieve information about the currently authenticated user.
    Requires a valid access token. Returns user details (id, username, email, role).
    """
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'email': user.email,
        'role': user.role,
        'two_factor_enabled': user.two_factor_enabled
    }), 200
