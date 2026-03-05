"""
Admin sidebar endpoint.

This module provides an endpoint to retrieve counts of various items
for display in the admin sidebar (badges for new donations, active drives,
unverified news, and new volunteers). Requires authentication and admin/moderator role.
"""

from flask import jsonify
from flask_jwt_extended import jwt_required
from models import Donation, Drive, NewsArticle, Volunteer
from utils import role_required
from . import admin_bp

# -------------------------------
# API: Sidebar
# -------------------------------

@admin_bp.route('/sidebar', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_sidebar():
    """
    Retrieve counts for admin sidebar badges.
    Returns JSON with counts of:
        - new donations (status 'ожидает')
        - active drives (status 'активен')
        - unverified news (is_verified=False)
        - new volunteers (status 'новый')
    Requires authentication and admin/moderator role.
    """
    count_new_donations = Donation.query.filter_by(status='ожидает').count()
    count_active_drives = Drive.query.filter_by(status='активен').count()
    count_not_verified_news = NewsArticle.query.filter_by(is_verified=False).count()
    count_new_volunteers = Volunteer.query.filter_by(status='новый').count()

    return jsonify({
        'count_new_donations': count_new_donations,
        'count_active_drives': count_active_drives,
        'count_not_verified_news': count_not_verified_news,
        'count_new_volunteers': count_new_volunteers
    }), 200
