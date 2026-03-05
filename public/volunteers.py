"""
Public API endpoints for volunteer applications.

This module provides a route to submit volunteer requests.
All endpoints are accessible without authentication.
"""

from flask import request, jsonify
from forms import VolunteerForm
from models import db, Volunteer
from utils import update_setting
from . import public_bp

# -------------------------------
# API: Volunteers
# -------------------------------

@public_bp.route('/volunteers', methods=['POST'])
def create_volunteer():
    """
    Public endpoint to submit a volunteer application.
    Expects JSON with volunteer details: name, email, phone, city, skills, can_deliver.
    Returns the created volunteer ID and a success message.
    No authentication required.
    """
    data = request.get_json()
    form = VolunteerForm(data=data)
    # if not form.validate():
    #     return jsonify({'errors': form.errors}), 400
    
    volunteer = Volunteer(
        name=form.name.data,
        email=form.email.data,
        phone=form.phone.data,
        city=form.city.data,
        skills=form.skills.data,
        can_deliver=form.can_deliver.data,
        status='новый'
    )
    db.session.add(volunteer)
    db.session.commit()
    
    # Update volunteer count stat
    count_volunteers = Volunteer.query.count()
    update_setting('count_volunteers', str(count_volunteers))
    
    return jsonify({'message': 'Заявка отправлена', 'id': volunteer.id}), 201
