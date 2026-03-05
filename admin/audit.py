"""
Admin audit logs endpoint.

This module provides a route for retrieving paginated audit logs.
Accessible only by users with admin role.
"""

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from models import AuditLog
from utils import role_required
from . import admin_bp

# -------------------------------
# API: Audit logs
# -------------------------------

@admin_bp.route('/audit', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_audit_logs():
    """
    Retrieve paginated list of audit logs with optional user filter.
    Query parameters:
        - page (int, default=1): page number
        - per_page (int, default=20): items per page
        - user_id (int, optional): filter logs by specific user ID
    Returns JSON with items, total count, current page, and total pages.
    Requires authentication and admin role.
    """
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    user_id = request.args.get('user_id', type=int)

    query = AuditLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page)

    logs = [{
        'id': log.id,
        'user_id': log.user_id,
        'username': log.username,
        'action': log.action,
        'details': log.details,
        'ip_address': log.ip_address,
        'created_at': log.created_at.isoformat()
    } for log in pagination.items]

    return jsonify({
        'items': logs,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200
