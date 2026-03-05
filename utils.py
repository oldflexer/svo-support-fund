"""
Utility functions for the application.

This module provides commonly used helpers:
- role_required: decorator to restrict access based on user roles.
- log_action: function to record user actions in the audit log.
"""
from datetime import datetime
from functools import wraps
from flask import request, jsonify
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
