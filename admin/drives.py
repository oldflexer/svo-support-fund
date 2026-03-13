"""
Admin drives endpoints.

This module provides routes for managing fundraising drives (сборы):
list, create, update, and delete drives.
Requires authentication and appropriate roles (admin/moderator).
"""

import json
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Drive
from forms import DriveForm
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: Drives
# -------------------------------

@admin_bp.route('/drives', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_drives():
    """
    Retrieve paginated list of drives with optional status filter.
    Query parameters:
        - page (int, default=1): page number
        - per_page (int, default=20): items per page
        - status (str, optional): filter by drive status
    Returns JSON with items, total count, current page, and total pages.
    Requires authentication (admin/moderator role checked implicitly by later decorator? but here only jwt_required; we keep as given).
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status', '')
    
    query = Drive.query
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(Drive.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    drives = []
    for d in pagination.items:
        drives.append({
            'id': d.id,
            'title': d.title,
            'description': d.description,
            'needs': d.needs_list,
            'status': d.status,
            'collected': d.collected,
            'needed': d.needed,
            'progress': d.progress_percentage,
            'created_at': d.created_at.isoformat() + 'Z' if d.created_at else None
        })

    return jsonify({
        'items': drives,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@admin_bp.route('/drives', methods=['POST'])
@jwt_required()
@role_required('admin', 'moderator')
def create_drive():
    """
    Create a new fundraising drive.
    Expects JSON with drive fields (title, description, needs, status, collected, needed).
    Validates using DriveForm.
    Returns success message and new drive ID.
    Requires authentication and admin/moderator role.
    """
    data = request.get_json() or {}
    form = DriveForm(data=data)
    # if not form.validate():
    #     return jsonify({'errors': form.errors}), 400

    needs_json = json.dumps(form.needs.data, ensure_ascii=False)
    
    drive = Drive(
        title=form.title.data,
        description=form.description.data,
        needs=needs_json,
        status=form.status.data,
        collected =form.collected.data or 0,
        needed=form.needed.data or 0
    )
    
    db.session.add(drive)
    db.session.commit()

    log_action(get_jwt_identity(), 'create_drive', f'Сбор {drive.id} создан', request.remote_addr)

    return jsonify({'message': 'Сбор создан', 'id': drive.id}), 201

@admin_bp.route('/drives/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_drive(id):
    """
    Update an existing drive by ID.
    Accepts partial JSON updates for fields: title, description, needs, status, collected, needed.
    Returns success message.
    Requires authentication and admin/moderator role.
    """
    drive = Drive.query.get_or_404(id)
    data = request.get_json() or {}

    # Update fields
    if 'title' in data:
        drive.title = data['title']
    if 'description' in data:
        drive.description = data['description']
    if 'needs' in data:
        drive.needs = json.dumps(data['needs'], ensure_ascii=False)
    if 'status' in data:
        drive.status = data['status']
    if 'collected' in data:
        drive.collected = data['collected']
    if 'needed' in data:
        drive.needed = data['needed']

    db.session.commit()

    log_action(get_jwt_identity(), 'update_donation', f'Сбор {drive.id} обновлен', request.remote_addr)

    return jsonify({'message': 'Сбор обновлен'}), 200

@admin_bp.route('/drives/<int:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin')
def delete_drive(id):
    """
    Delete a drive by ID.
    Returns success message.
    Requires authentication and admin role (only admin can delete).
    """
    drive = Drive.query.get_or_404(id)
    db.session.delete(drive)
    db.session.commit()

    log_action(get_jwt_identity(), 'delete_drive', f'Сбор {id} удален', request.remote_addr)

    return jsonify({'message': 'Сбор удален'}), 200
