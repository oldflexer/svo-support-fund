from datetime import datetime
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Setting
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: Settings
# -------------------------------

@admin_bp.route('/settings', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_settings():
    """Retrieve all settings as key-value pairs."""
    settings = Setting.query.all()
    result = {s.key: s.value for s in settings}
    return jsonify(result), 200

@admin_bp.route('/settings', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_settings():
    """Update multiple settings at once. Expects JSON object with keys and values."""
    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({'error': 'Expected JSON object'}), 400

    for key, value in data.items():
        setting = Setting.query.get(key)
        if setting:
            setting.value = str(value)  # ensure string
        else:
            setting = Setting(key=key, value=str(value))
            db.session.add(setting)
    db.session.commit()
    return jsonify({'message': 'Settings updated'}), 200