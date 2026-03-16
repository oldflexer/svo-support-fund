"""
Public API endpoints for donations.

This module provides public routes for creating donations.
All endpoints are accessible without authentication.
"""

from flask import request, jsonify
from forms import DonationForm
from models import db, Donation, Drive
from utils import update_setting
from . import public_bp

# -------------------------------
# API: Donations
# -------------------------------

@public_bp.route('/donations', methods=['POST'])
def create_donation():
    """
    Public endpoint to create a new donation.
    Expects JSON with donor name, amount, optional message and anonymity flag.
    Returns the created donation ID and a success message.
    No authentication required.
    """
    data = request.get_json()
    form = DonationForm(data=data, meta={'csrf': False})
    if not form.validate():
        return jsonify({'errors': form.errors}), 400
    
    drive_id = data.get('drive_id')
    if drive_id is not None:
        drive = Drive.query.get(drive_id)
        if not drive:
            return jsonify({'error': 'Указанный сбор не существует'}), 400
        if drive.status != 'активен':
            return jsonify({'error': 'Выбранный сбор не активен'}), 400
    
    donation = Donation(
        donor_name=form.name.data,
        amount=form.amount.data,
        message=form.message.data,
        is_anonymous=form.is_anonymous.data,
        status='ожидает',
        drive_id=drive_id
    )
    db.session.add(donation)
    db.session.commit()
    
    # Update stats
    sum_donation = db.session.query(db.func.sum(Donation.amount)).scalar()
    update_setting('sum_donation', str(sum_donation))
    
    return jsonify({'message': 'Пожертвование принято', 'id': donation.id}), 201
