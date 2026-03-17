from datetime import datetime, timedelta
from flask import jsonify, request
from flask_jwt_extended import jwt_required
from models import Donation, Volunteer
from utils import role_required
from . import admin_bp

@admin_bp.route('/notifications', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_notifications():
    last_check = request.args.get('last_check')
    try:
        if last_check:
            last_check_dt = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
        else:
            last_check_dt = datetime.utcnow() - timedelta(days=1)
    except:
        last_check_dt = datetime.utcnow() - timedelta(days=1)

    new_donations = Donation.query.filter(
        Donation.status == 'ожидает',
        Donation.created_at > last_check_dt
    ).count()

    new_volunteers = Volunteer.query.filter(
        Volunteer.status == 'новый',
        Volunteer.created_at > last_check_dt
    ).count()

    return jsonify({
        'new_donations': new_donations,
        'new_volunteers': new_volunteers,
        'server_time': datetime.utcnow().isoformat() + 'Z'
    }), 200
