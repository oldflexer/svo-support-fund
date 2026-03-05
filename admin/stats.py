"""
Admin statistics endpoints.

This module provides an endpoint to retrieve comprehensive statistics
about donations, drives, news, and volunteers for the admin panel.
Requires authentication and admin/moderator role.
"""

from flask import jsonify
from flask_jwt_extended import jwt_required
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
    count_donations = Donation.query.count()
    count_new_donations = Donation.query.filter_by(status='ожидает').count()
    count_processed_donations = Donation.query.filter_by(status='обработано').count()
    count_sent_donations = Donation.query.filter_by(status='отправлено').count()
    min_donation = db.session.query(db.func.min(Donation.amount)).scalar() or 0
    max_donation = db.session.query(db.func.max(Donation.amount)).scalar() or 0
    sum_donation = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    avg_donation = db.session.query(db.func.avg(Donation.amount)).scalar() or 0

    # Drives
    count_drives = Drive.query.count()
    count_active_drives = Drive.query.filter_by(status='активен').count()
    count_completed_drives = Drive.query.filter_by(status='завершен').count()
    count_suspended_drives = Drive.query.filter_by(status='приостановлен').count()
    sum_collected_drives = db.session.query(db.func.sum(Drive.collected)).scalar() or 0
    sum_needed_drives = db.session.query(db.func.sum(Drive.needed)).scalar() or 0

    # News
    count_news = NewsArticle.query.count()
    count_verified_news = NewsArticle.query.filter_by(is_verified=True).count()
    count_not_verified_news = NewsArticle.query.filter_by(is_verified=False).count()
    count_category_news = NewsArticle.query.filter_by(category='новости', is_verified=True).count()
    count_category_report = NewsArticle.query.filter_by(category='отчёт', is_verified=True).count()
    count_category_story = NewsArticle.query.filter_by(category='история', is_verified=True).count()
    
    top_news = NewsArticle.query.filter_by(is_verified=True).order_by(NewsArticle.views_count.desc()).limit(3).all()
    top_news = [{
        'id': n.id,
        'title': n.title,
        'views_count': n.views_count
    } for n in top_news]

    # Volunteers
    count_volunteers = Volunteer.query.count()
    count_new_volunteers = Volunteer.query.filter_by(status='новый').count()
    count_in_touch_volunteers = Volunteer.query.filter_by(status='связались').count()
    count_active_volunteers = Volunteer.query.filter_by(status='активен').count()
    count_archive_volunteers = Volunteer.query.filter_by(status='архив').count()
    
    return jsonify({
        'donations': {
            'count_donations': count_donations,
            'count_new_donations': count_new_donations,
            'count_processed_donations': count_processed_donations,
            'count_sent_donations': count_sent_donations,
            'min_donation': min_donation,
            'max_donation': max_donation,
            'sum_donation': sum_donation,
            'avg_donation': avg_donation
        },
        'drives': {
            'count_drives': count_drives,
            'count_active_drives': count_active_drives,
            'count_completed_drives': count_completed_drives,
            'count_suspended_drives': count_suspended_drives,
            'sum_collected_drives': sum_collected_drives,
            'sum_needed_drives': sum_needed_drives
        },
        'news': {
            'count_news': count_news,
            'count_verified_news': count_verified_news,
            'count_not_verified_news': count_not_verified_news,
            'count_category_news': count_category_news,
            'count_category_report': count_category_report,
            'count_category_story': count_category_story,
            'top_news': top_news
        },
        'volunteers': {
            'count_volunteers': count_volunteers,
            'count_new_volunteers': count_new_volunteers,
            'count_in_touch_volunteers': count_in_touch_volunteers,
            'count_active_volunteers': count_active_volunteers,
            'count_archive_volunteers': count_archive_volunteers
        }
    }), 200
