"""
Public API endpoints for general statistics.

This module provides a route to retrieve overall statistics
    such as total donations and volunteer count.
All endpoints are accessible without authentication.
"""

from flask import jsonify
from models import db, Donation, Volunteer, Setting
from utils import get_setting
from . import public_bp

# -------------------------------
# API: Stats
# -------------------------------

@public_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Public endpoint to retrieve general statistics.
    Returns cached total donation amount (sum_donation) and total number of volunteers (count_volunteers) from settings.
    Values are updated periodically for performance.
    No authentication required.
    """
    sum_donation = get_setting('sum_donation')
    count_volunteers = get_setting('count_volunteers')

    return jsonify({
        'sum_donation': sum_donation,
        'count_volunteers': count_volunteers
    }), 200
