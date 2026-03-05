"""
Authentication blueprint initialization.

This module creates the 'auth' blueprint with URL prefix '/api/auth'
and imports submodules containing route definitions for:
- authentication (login, logout, token refresh, current user)
- two-factor authentication (2FA) management (setup, enable, disable, backup codes)
"""

from flask import Blueprint

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

from . import authentication, management
