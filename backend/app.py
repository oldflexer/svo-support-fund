"""
Main Flask application with modular structure
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
from schemas import validate_request_data, SCHEMAS
from marshmallow import ValidationError
from middleware import validate_json, validate_query_params
from models import NewsArticle, UnitRequest, db, bcrypt, AdminUser, AssistanceType, Donation, Volunteer, Delivery, AuditLog, EquipmentRequest
from two_factor import TwoFactorAuth, require_2fa_setup, require_2fa_enabled
from config import Config
from auth import (
    create_access_token, create_refresh_token, verify_token,
    login_required, role_required, log_audit, validate_password,
    AuthError
)
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True)
db.init_app(app)
bcrypt.init_app(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database with test data
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create default admin if none exists
        if AdminUser.query.count() == 0:
            admin = AdminUser(
                username='admin',
                email='admin@zaschitnikam.ru',
                full_name='Главный администратор',
                role='admin',
                is_active=True
            )
            admin.set_password('Admin123!')
            db.session.add(admin)
            db.session.commit()

# Import and register modules
from backend.api.public import public_bp
from backend.api.auth import auth_bp
from backend.api.admin import admin_bp
from backend.api.admin_extended import admin_bp as admin_extended_bp
from backend.api.admin_donations import admin_bp as admin_donations_bp
from backend.api.admin_users import admin_bp as admin_users_bp
from backend.api.admin_audit import admin_bp as admin_audit_bp

app.register_blueprint(public_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(admin_extended_bp, url_prefix='/api/admin')
app.register_blueprint(admin_donations_bp, url_prefix='/api/admin')
app.register_blueprint(admin_users_bp, url_prefix='/api/admin')
app.register_blueprint(admin_audit_bp, url_prefix='/api/admin')

# Public endpoints
@app.route('/')
def home():
    return jsonify({
        'message': 'Свояченикам.рф API is running',
        'version': '1.0.0',
        'endpoints': {
            'public': '/api',
            'auth': '/api/auth',
            'admin': '/api/admin'
        }
    })

# Health check endpoint
@app.route('/health')
def health_check():
                return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    })

# Error handlers
@app.errorhandler(AuthError)
def handle_auth_error(ex):
    response = jsonify(ex.error)
    response.status_code = ex.status_code
    return response
@app.errorhandler(ValidationError)
def handle_validation_error(ex):
    return jsonify({
        'success': False,
        'message': 'Validation error',
        'errors': ex.messages
    }), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'message': 'Resource not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'message': 'Internal server error'
    }), 500

# Main entry point
if __name__ == '__main__':
    # Initialize database
    init_db()

    # Run the app
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )

