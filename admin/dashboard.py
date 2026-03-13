"""
Admin dashboard endpoints.

This module provides an endpoint to retrieve aggregated statistics and chart data
for the admin dashboard, including donation totals, trends, recent donations, and volunteer counts.
Requires authentication and admin/moderator role.
"""

from datetime import datetime, timedelta, UTC
from flask import jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, cast, Date
from models import db, Donation, Volunteer
from utils import role_required
from . import admin_bp

# -------------------------------
# API: Dashboaard
# -------------------------------

@admin_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_dashboard():
    """
    Retrieve dashboard statistics for admin panel.
    Returns JSON with:
        - donations: total count, total amount, weekly change percentage, recent donations list
        - volunteers: total count
        - chart: labels (dates) and data (donation amounts) for the last 7 days
    Requires authentication and admin/moderator role.
    """
    # Total donations
    sum_donations = db.session.query(db.func.sum(Donation.amount)).scalar() or 0

    # Date definition for future calculations
    datetime_now = datetime.now(UTC).replace(tzinfo=None)
    datetime_week_ago = datetime_now - timedelta(days=7)
    datetime_two_weeks_ago = datetime_now - timedelta(days=14)

    # Change since last week
    sum_donations_current_week = db.session.query(db.func.sum(Donation.amount)).filter(Donation.created_at >= datetime_week_ago).scalar() or 0
    sum_donations_previous_week = db.session.query(db.func.sum(Donation.amount)).filter(Donation.created_at.between(datetime_two_weeks_ago, datetime_week_ago)).scalar() or 0

    if sum_donations_previous_week:
        change_sum_donations = (sum_donations_current_week - sum_donations_previous_week) / sum_donations_previous_week
    else:
        change_sum_donations = 0

    # Donations count
    count_donations = Donation.query.count()

    # Volunteers count
    count_volunteers = Volunteer.query.count()

    # For donations chart data (last 7 days)

    daily_totals = db.session.query(
        func.date(Donation.created_at).label('day'),
        func.sum(Donation.amount).label('total')
    ).filter(
        Donation.created_at >= datetime_week_ago
    ).group_by(
        func.date(Donation.created_at)
    ).all()

    total_by_day = {row.day: row.total for row in daily_totals}

    chart_donations_dates = []
    chart_donations_amounts = []
    for i in range(6, -1, -1):
        day = (datetime_now - timedelta(days=i)).date()
        day_str = day.isoformat()
        chart_donations_dates.append(day.strftime('%d.%m'))
        chart_donations_amounts.append(total_by_day.get(day_str, 0))

    # Recent donations
    recent_donations = Donation.query.order_by(Donation.created_at.desc()).limit(10).all()
    recent_donations = [{
        'id': d.id,
        'donor_name': 'Аноним' if d.is_anonymous else d.donor_name,
        'amount': d.amount,
        'status': d.status,
        'created_at': d.created_at.isoformat() + 'Z'
    } for d in recent_donations]

    return jsonify({
        'donations': {
            'total': count_donations,
            'total_amount': sum_donations,
            'change': change_sum_donations,
            'recent_donations': recent_donations
        },
        'volunteers': {
            'total': count_volunteers
        },
        'chart': {
            'labels': chart_donations_dates,
            'datasets': [{'label': 'Сумма пожертвований', 'data': chart_donations_amounts}]
        }
    }), 200
