"""
2FA (Two-Factor Authentication) endpoints.

This module provides routes for managing two-factor authentication:
- Verify 2FA during login.
- Setup, enable, disable 2FA.
- Regenerate backup codes.

All routes except verify_2fa require JWT authentication.
"""

import json
import io
import base64
import secrets
from datetime import datetime

import pyotp
import qrcode
from flask import request, jsonify
from flask_jwt_extended import jwt_required, decode_token, create_access_token, create_refresh_token
from models import db, User
from utils import get_jwt_identity, log_action
from . import auth_bp

# -------------------------------
# API: 2FA management
# -------------------------------

@auth_bp.route('/2fa/verify', methods=['POST'])
def verify_2fa():
    """
    Verify a 2FA token or backup code during login.
    Expects JSON with temp_token, token, and optional use_backup flag.
    Returns full access/refresh tokens and user data if verification succeeds.
    """
    data = request.get_json() or {}
    temp_token = data.get('temp_token')
    token = data.get('token')
    use_backup = data.get('use_backup', False)
    
    if not temp_token or not token:
        return jsonify({'error': 'Отсутствуют параметры'}), 400
    
    # Decode temp token
    try:
        decoded = decode_token(temp_token)
        user_id = decoded['sub']
        if not decoded.get('requires_2fa'):
            return jsonify({'error': 'Неверный токен'}), 400
    except Exception:
        return jsonify({'error': 'Недействительный токен'}), 400
    
    user = User.query.get(user_id)
    if not user or not user.two_factor_enabled:
        return jsonify({'error': '2FA не настроена'}), 400
    
    # Verify token or backup code
    valid = False
    if use_backup and user.backup_codes:
        codes = json.loads(user.backup_codes)
        if token in codes:
            codes.remove(token)
            user.backup_codes = json.dumps(codes)
            valid = True
    else:
        if user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            valid = totp.verify(token)
    
    if not valid:
        return jsonify({'error': 'Неверный код'}), 400
    
    # Issue full tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    log_action(get_jwt_identity(), 'login_2fa', 'Успешный вход с 2FA', request.remote_addr)
    
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

@auth_bp.route('/2fa/setup', methods=['POST'])
@jwt_required()
def setup_2fa():
    """
    Initialize 2FA setup for the current user.
    Generates a TOTP secret, backup codes, and a QR code.
    Returns QR code image (base64), secret, and backup codes.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Generate TOTP secret
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.session.commit()
    
    # Generate provisioning URI
    issuer = 'ЗащитимРодину'
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)
    
    # Generate QR code
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(stream=buf, kind='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    qr_dataurl = f"data:image/png;base64,{qr_base64}"
    
    # Generate backup codes (5 random 8-digit numbers)
    backup_codes = [''.join(secrets.choice('0123456789') for _ in range(8)) for _ in range(5)]
    user.backup_codes = json.dumps(backup_codes)
    db.session.commit()

    log_action(get_jwt_identity(), 'setup_2fa', 'Установлена двухфакторная аутентификация', request.remote_addr)
    
    return jsonify({
        'qr_code': qr_dataurl,
        'secret': secret,
        'backup_codes': backup_codes
    }), 200

@auth_bp.route('/2fa/enable', methods=['POST'])
@jwt_required()
def enable_2fa():
    """
    Enable 2FA after successful verification of a test token.
    Expects JSON with 'token' (6-digit code from authenticator app).
    Returns success message.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.totp_secret:
        return jsonify({'error': 'Сначала выполните настройку 2FA'}), 400
    
    data = request.get_json() or {}
    token = data.get('token')
    if not token:
        return jsonify({'error': 'Требуется код подтверждения'}), 400
    
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(token):
        return jsonify({'error': 'Неверный код'}), 400
    
    user.two_factor_enabled = True
    db.session.commit()
    
    log_action(get_jwt_identity(), '2fa_enable', 'Включена двухфакторная аутентификация', request.remote_addr)
    
    return jsonify({'message': '2FA успешно включена'}), 200

@auth_bp.route('/2fa/disable', methods=['POST'])
@jwt_required()
def disable_2fa():
    """
    Disable 2FA for the current user.
    Requires either password or current 2FA token/backup code for verification.
    Returns success message.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json() or {}
    password = data.get('password')
    token = data.get('token')
    
    # Verify either password or current 2FA code
    valid = False
    if password and user.check_password(password):
        valid = True
    elif token and user.totp_secret:
        totp = pyotp.TOTP(user.totp_secret)
        valid = totp.verify(token)
    elif token and user.backup_codes:
        codes = json.loads(user.backup_codes)
        if token in codes:
            codes.remove(token)
            user.backup_codes = json.dumps(codes)
            valid = True
    
    if not valid:
        return jsonify({'error': 'Не удалось подтвердить личность'}), 400
    
    user.two_factor_enabled = False
    user.totp_secret = None
    user.backup_codes = None
    db.session.commit()
    
    log_action(get_jwt_identity(), '2fa_disable', 'Отключена двухфакторная аутентификация', request.remote_addr)
    
    return jsonify({'message': '2FA отключена'}), 200

@auth_bp.route('/2fa/backup-codes', methods=['POST'])
@jwt_required()
def regenerate_backup_codes():
    """
    Generate a new set of backup codes for the current user.
    Replaces existing backup codes.
    Returns the new backup codes.
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    backup_codes = [''.join(secrets.choice('0123456789') for _ in range(8)) for _ in range(5)]
    user.backup_codes = json.dumps(backup_codes)
    db.session.commit()
    
    log_action(get_jwt_identity(), '2fa_regenerate_backup', 'Сгенерированы новые резервные коды', request.remote_addr)
    
    return jsonify({'backup_codes': backup_codes}), 200
