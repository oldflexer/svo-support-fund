"""
Admin volunteers endpoints.

This module provides routes for listing and updating volunteer applications.
Requires authentication and admin/moderator role.
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Volunteer
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: Volunteers
# -------------------------------

@admin_bp.route('/volunteers', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_volunteers():
    """
    Retrieve paginated list of volunteers with optional status filter.
    Query parameters:
        - page (int, default=1): page number
        - per_page (int, default=20): items per page
        - status (str, optional): filter by volunteer status
    Returns JSON with items, total count, current page, and total pages.
    Requires authentication and admin/moderator role.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
        
    query = Volunteer.query
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(Volunteer.created_at.desc()).paginate(page=page, per_page=per_page)
    
    volunteers = [{
        'id': v.id,
        'name': v.name,
        'email': v.email,
        'phone': v.phone,
        'city': v.city,
        'skills': v.skills,
        'can_deliver': v.can_deliver,
        'status': v.status,
        'created_at': v.created_at.isoformat()
    } for v in pagination.items]
    
    return jsonify({
        'items': volunteers,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@admin_bp.route('/volunteers/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_volunteer(id):
    """
    Update volunteer status by ID.
    Expects JSON with 'status' field.
    Logs the action with current user and IP.
    Returns success message or error.
    Requires authentication and admin/moderator role.
    """
    volunteer = Volunteer.query.get_or_404(id)
    data = request.get_json() or {}
    if data is None:
        return jsonify({'error': 'Требуется JSON'}), 400
    if 'status' in data:
        volunteer.status = data['status']
        db.session.commit()

        log_action(get_jwt_identity(), 'update_volunteer', f"Волонтёр {volunteer.id} обновлен {data['status']}", request.remote_addr)

        return jsonify({'message': 'Статус обновлен'}), 200
    return jsonify({'error': 'Поле status не найдено'}), 400
