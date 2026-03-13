from datetime import datetime
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Setting
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: Settings
# -------------------------------

ALLOWED_SETTINGS = {
    # Statistics (numbers)
    'sum_donation': (int, float),
    'count_volunteers': (int, float),

    # Main settings (strings)
    'site_title': str,
    'site_short_name': str,
    'contact_email': str,
    'contact_phone': str,
    'contact_address': str,

    # Social networks (strings)
    'social_vk': str,
    'social_telegram': str,
    'social_max': str,

    # Bank details (strings)
    'inn': str,
    'ogrn': str,
    'bank_account': str,
    'bank_name': str,
    'corr_account': str,
    'bik': str,

    # Module toggles (booleans)
    'enable_donations': bool,
    'enable_volunteers': bool,
    'enable_news': bool,
}

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

    # Check that all provided keys are allowed
    for key in data:
        if key not in ALLOWED_SETTINGS:
            return jsonify({'error': f'Invalid settings key: {key}'}), 400

    # Validate value types
    for key, value in data.items():
        expected_type = ALLOWED_SETTINGS[key]
        # Check that the value matches the expected type
        if not isinstance(value, expected_type):
            # Attempt conversion for numbers if a string is provided
            if expected_type in (int, float) and isinstance(value, str):
                try:
                    if expected_type == int:
                        value = int(value)
                    else:
                        value = float(value)
                    data[key] = value
                except ValueError:
                    return jsonify({'error': f'Field {key} must be a number'}), 400
            else:
                type_name = expected_type.__name__ if hasattr(expected_type, '__name__') else str(expected_type)
                return jsonify({'error': f'Field {key} must be of type {type_name}'}), 400

    # Save settings
    for key, value in data.items():
        # Store boolean values as strings "true"/"false"
        if isinstance(value, bool):
            value = 'true' if value else 'false'
        else:
            value = str(value)

        setting = Setting.query.get(key)
        if setting:
            setting.value = value
        else:
            setting = Setting(key=key, value=value)
            db.session.add(setting)

    db.session.commit()
    return jsonify({'message': 'Settings updated'}), 200
