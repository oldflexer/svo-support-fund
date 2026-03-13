"""
Admin donations endpoints.

Provides routes for listing and updating donations.
Requires authentication and admin/moderator role.
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Donation
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: Donations
# -------------------------------

@admin_bp.route('/donations', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_donations():
    """
    Retrieve paginated list of donations with optional status filter.
    Query parameters:
        - page (int, default=1): page number
        - status (str, optional): filter by donation status
    Returns JSON with items, total count, current page, and total pages.
    Requires authentication and admin/moderator role.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
        
    query = Donation.query
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Donation.created_at.desc()).paginate(page=page, per_page=per_page)
    
    donations = [{
        'id': d.id,
        'donor_name': 'Аноним' if d.is_anonymous else d.donor_name,
        'amount': d.amount,
        'message': d.message,
        'is_anonymous': d.is_anonymous,
        'status': d.status,
        'created_at': d.created_at.isoformat()
    } for d in pagination.items]

    return jsonify({
        'items': donations,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@admin_bp.route('/donations/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_donation(id):
    """
    Update donation status by ID.
    Expects JSON with 'status' field.
    Logs the action with current user and IP.
    Returns success message or error.
    Requires authentication and admin/moderator role.
    """
    donation = Donation.query.get_or_404(id)
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Требуется JSON'}), 400
    if 'status' in data:
        donation.status = data['status']
        db.session.commit()

        log_action(get_jwt_identity(), 'update_donation', f"Пожертвование {donation.id} обновлено {data['status']}", request.remote_addr)

        return jsonify({'message': 'Статус обновлен'}), 200
    return jsonify({'error': 'Поле status не найдено'}), 400
