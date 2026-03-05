"""
Public API blueprint initialization.

This module creates the 'public' blueprint and imports submodules
containing route definitions for public endpoints (stats, volunteers, donations).
All routes registered on this blueprint are publicly accessible without authentication.
"""

from flask import Blueprint

public_bp = Blueprint('public', __name__, url_prefix='/api/public')

from . import stats, drives, news, volunteers, donations
