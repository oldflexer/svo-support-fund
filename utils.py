"""
Utility functions for the application.

This module provides commonly used helpers:
- role_required: decorator to restrict access based on user roles.
- log_action: function to record user actions in the audit log.
"""
import os
from datetime import datetime
from functools import wraps
from PIL import Image
from flask import current_app, request, jsonify
from flask_jwt_extended import get_jwt_identity, jwt_required
from models import db, User, AuditLog, Setting

# -------------------------------
# Helper functions
# -------------------------------

def role_required(*roles):
    """
    Decorator to restrict endpoint access based on user roles.
    Requires JWT authentication. The current user must have one of the allowed roles.
    """
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            if not user or not user.is_active or user.role not in roles:
                return jsonify({'error': 'Доступ запрещен'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_action(user_id, action, details='', ip=None):
    """
    Log an action to the audit log.
    If ip is not provided, uses request.remote_addr.
    """
    if ip is None:
        ip = request.remote_addr

    user = User.query.get(user_id)
    username = user.username if user else None

    log = AuditLog(user_id=user_id, username=username, action=action, details=details, ip_address=ip)
    db.session.add(log)
    db.session.commit()

def get_setting(key, default=None):
    setting = Setting.query.get(key)
    return setting.value if setting else default

def update_setting(key, value):
    setting = Setting.query.get(key)
    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()

def is_allowed_image(file_stream, filename):
    allowed_extensions = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS', set())
    allowed_mime_types = current_app.config.get('ALLOWED_IMAGE_MIME_TYPES', set())

    ext = os.path.splitext(filename)[1].lower()
    if ext not in allowed_extensions:
        return False, "Недопустимое расширение файла"

    try:
        file_stream.seek(0)
        img = Image.open(file_stream)

        if img.format is None:
            return False, "Не удалось определить формат изображения"
        
        mime_type = Image.MIME.get(img.format, '')

        if mime_type not in allowed_mime_types:
            return False, "Недопустимый тип изображения"
        
    except Exception:
        return False, "Файл не является изображением или повреждён"
    
    finally:
        file_stream.seek(0)

    return True, ""
