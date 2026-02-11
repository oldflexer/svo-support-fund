"""
API Blueprints initialization
"""

from flask import Blueprint
from flask_cors import CORS

# Create Blueprints
public_bp = Blueprint('public', __name__, url_prefix='/api')
auth_bp = Blueprint('auth', __name__, url_prefix='/api')
admin_bp = Blueprint('admin', __name__, url_prefix='/api')

# Import all API modules
from . import (
    public, auth, admin,
    admin_extended, admin_donations, admin_users, admin_audit
)

# Enable CORS for all API routes
CORS(public_bp, supports_credentials=True)
CORS(auth_bp, supports_credentials=True)
CORS(admin_bp, supports_credentials=True)

# Register all admin blueprints with sub-prefixes
def register_admin_blueprints(app):
    """Register all admin blueprints with /admin prefix"""
    app.register_blueprint(admin_bp, url_prefix='/api/admin')
    app.register_blueprint(admin_extended.admin_bp, url_prefix='/api/admin')
    app.register_blueprint(admin_donations.admin_bp, url_prefix='/api/admin')
    app.register_blueprint(admin_users.admin_bp, url_prefix='/api/admin')
    app.register_blueprint(admin_audit.admin_bp, url_prefix='/api/admin')

# Register public and auth blueprints
def register_public_blueprints(app):
    """Register public and auth blueprints"""
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)

# Health check endpoint
@public_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        from backend.models import db
        db.session.execute('SELECT 1')
        
        return jsonify({
            'success': True,
            'message': 'API is healthy',
            'status': 'operational'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'API health check failed: {str(e)}',
            'status': 'degraded'
        }), 503
