"""
Admin statistics endpoints.

This module provides an endpoint to retrieve comprehensive statistics
about donations, drives, news, and volunteers for the admin panel.
Requires authentication and admin/moderator role.
"""

from flask import jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func, case
from models import db, Donation, Drive, NewsArticle, Volunteer
from utils import role_required
from . import admin_bp

# -------------------------------
# API: Stats
# -------------------------------

@admin_bp.route('/stats', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_stats():
    """
    Retrieve detailed statistics for the admin panel.
    Returns JSON with aggregated data:
        - donations: total, new, processed, sent, min, max, sum, avg
        - drives: total, active, completed, suspended, sum collected, sum needed
        - news: total, verified, unverified, by category, top 3 viewed
        - volunteers: total, new, in touch, active, archive
    Requires authentication and admin/moderator role.
    """

    # Donations
    donation_agg = db.session.query(
        func.coalesce(func.count(Donation.id), 0).label('count'),
        func.coalesce(func.min(Donation.amount), 0).label('min'),
        func.coalesce(func.max(Donation.amount), 0).label('max'),
        func.coalesce(func.sum(Donation.amount), 0).label('sum'),
        func.coalesce(func.avg(Donation.amount), 0).label('avg')
    ).first()
    donation_agg = donation_agg._asdict() if donation_agg else {
        'count': 0, 'min': 0, 'max': 0, 'sum': 0, 'avg': 0
    }

    donation_status_counts = dict(
        db.session.query(Donation.status, func.count(Donation.id))
        .group_by(Donation.status).all()
    )

    # Drives
    drive_agg = db.session.query(
        func.coalesce(func.count(Drive.id), 0).label('count'),
        func.coalesce(func.sum(Drive.collected), 0).label('sum_collected'),
        func.coalesce(func.sum(Drive.needed), 0).label('sum_needed')
    ).first()
    drive_agg = drive_agg._asdict() if drive_agg else {
        'count': 0, 'sum_collected': 0, 'sum_needed': 0
    }

    drive_status_counts = dict(
        db.session.query(Drive.status, func.count(Drive.id))
        .group_by(Drive.status).all()
    )

    # Volunteers
    volunteer_agg = db.session.query(
        func.coalesce(func.count(Volunteer.id), 0).label('count')
    ).first()
    volunteer_agg = volunteer_agg._asdict() if volunteer_agg else {'count': 0}

    volunteer_status_counts = dict(
        db.session.query(Volunteer.status, func.count(Volunteer.id))
        .group_by(Volunteer.status).all()
    )

    # News
    news_agg = db.session.query(
        func.coalesce(func.count(NewsArticle.id), 0).label('count'),
        func.coalesce(func.sum(case((NewsArticle.is_verified == True, 1), else_=0)), 0).label('verified'),
        func.coalesce(func.sum(case((NewsArticle.is_verified == False, 1), else_=0)), 0).label('unverified')
    ).first()
    news_agg = news_agg._asdict() if news_agg else {
        'count': 0, 'verified': 0, 'unverified': 0
    }

    category_counts = dict(
        db.session.query(NewsArticle.category, func.count(NewsArticle.id))
        .filter(NewsArticle.is_verified == True)
        .group_by(NewsArticle.category).all()
    )

    top_news = [
        {'id': n.id, 'title': n.title, 'views_count': n.views_count}
        for n in NewsArticle.query.filter_by(is_verified=True)
        .order_by(NewsArticle.views_count.desc())
        .limit(3).all()
    ]

    return jsonify({
        'donations': {
            'count_donations': donation_agg['count'],
            'count_new_donations': donation_status_counts.get('ожидает', 0),
            'count_processed_donations': donation_status_counts.get('обработано', 0),
            'count_sent_donations': donation_status_counts.get('отправлено', 0),
            'min_donation': donation_agg['min'],
            'max_donation': donation_agg['max'],
            'sum_donation': donation_agg['sum'],
            'avg_donation': donation_agg['avg'],
        },
        'drives': {
            'count_drives': drive_agg['count'],
            'count_active_drives': drive_status_counts.get('активен', 0),
            'count_completed_drives': drive_status_counts.get('завершен', 0),
            'count_suspended_drives': drive_status_counts.get('приостановлен', 0),
            'sum_collected_drives': drive_agg['sum_collected'],
            'sum_needed_drives': drive_agg['sum_needed'],
        },
        'news': {
            'count_news': news_agg['count'],
            'count_verified_news': news_agg['verified'],
            'count_not_verified_news': news_agg['unverified'],
            'count_category_news': category_counts.get('новости', 0),
            'count_category_report': category_counts.get('отчёт', 0),
            'count_category_story': category_counts.get('история', 0),
            'top_news': top_news,
        },
        'volunteers': {
            'count_volunteers': volunteer_agg['count'],
            'count_new_volunteers': volunteer_status_counts.get('новый', 0),
            'count_in_touch_volunteers': volunteer_status_counts.get('связались', 0),
            'count_active_volunteers': volunteer_status_counts.get('активен', 0),
            'count_archive_volunteers': volunteer_status_counts.get('архив', 0),
        }
    }), 200