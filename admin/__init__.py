"""
Admin blueprint initialization.

This module creates the 'admin' blueprint with URL prefix '/api/admin'
and imports submodules containing route definitions for administrative
functionality: sidebar, dashboard, stats, donations, drives, news, upload,
volunteers, users, audit, and settings.
"""

from flask import Blueprint

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')

from . import sidebar, dashboard, stats, donations, drives, news, upload, volunteers, users, audit, settings, notifications
