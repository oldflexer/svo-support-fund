"""
API Blueprints initialization
"""

from flask import Blueprint

# Create Blueprints
public_bp = Blueprint('public', __name__, url_prefix='/api')
auth_bp = Blueprint('auth', __name__, url_prefix='/api')
admin_bp = Blueprint('admin', __name__, url_prefix='/api')

# Import views after blueprint creation to avoid circular imports
from . import public, auth, admin
