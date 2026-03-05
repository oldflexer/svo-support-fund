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
    total_donated = get_setting('total_donated', '0')
    total_volunteers = get_setting('total_volunteers', '0')
    print(total_donated, total_volunteers)
    return jsonify({
        'total_donated': int(total_donated),
        'total_volunteers': int(total_volunteers)
    }), 200

@admin_bp.route('/settings', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_settings():
    data = request.get_json() or {}
    for key, value in data.items():
        update_setting(key, str(value))

    log_action(get_jwt_identity(), 'update_settings', 'Настройки обновлены', request.remote_addr)

    return jsonify({'message': 'Настройки обновлены'}), 200

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