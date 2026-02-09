# coding: utf-8
"""
Admin API endpoints for managing charitable foundation operations
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from sqlalchemy import or_, func
from datetime import datetime, timedelta
import pyotp
import qrcode
import io
import base64

from backend.middleware import login_required, admin_required
from backend.utils.helpers import paginate_results, format_date, format_currency
from backend.config import Config
from backend.models import AdminUser, UnitRequest, Donation, AuditLog, TwoFactor

admin_bp = Blueprint('admin', __name__)

# Unit Requests Endpoints
@admin_bp.route('/api/admin/unit-requests', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_unit_requests():
    """Get paginated list of unit requests"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status', None, type=str)
        search = request.args.get('search', None, type=str)
        
        query = UnitRequest.query
        
        if status:
            query = query.filter(UnitRequest.status == status)
        
        if search:
            query = query.filter(
                or_(
                    UnitRequest.unit_name.ilike(f"%{search}%")
                )
            )
        
        pagination = paginate_results(query, page, per_page)
        
        # Calculate progress for each request
        requests = []
        for request_item in pagination.items:
            collected = 0
            donations = Donation.query.filter(
                Donation.unit_request_id == request_item.id,
                Donation.status == 'обработано'
            ).all()
            for donation in donations:
                collected += donation.amount
            
            requests.append({
                'id': request_item.id,
                'unit_name': request_item.unit_name,
                'unit_type': request_item.unit_type,
                'location': request_item.location,
                'description': request_item.description,
                'needed_amount': request_item.needed_amount,
                'status': request_item.status,
                'created_at': format_date(request_item.created_at),
                'collected_amount': collected,
                'progress_percentage': min(100, int((collected / request_item.needed_amount) * 100)) if request_item.needed_amount > 0 else 0
            })
        
        return jsonify({
            'success': True,
            'data': {
                'requests': requests,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting unit requests: {str(e)}'}), 500

@admin_bp.route('/api/admin/unit-requests/<int:request_id>', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_unit_request(request_id):
    """Get detailed information about a specific unit request"""
    try:
        request_item = UnitRequest.query.get(request_id)
        if not request_item:
            return jsonify({'success': False, 'message': 'Unit request not found'}), 404
        
        # Get donations for this request
        donations = []
        donations_query = Donation.query.filter(
            Donation.unit_request_id == request_id
        ).order_by(Donation.created_at.desc()).all()
        
        for donation in donations_query:
            donations.append({
                'id': donation.id,
                'donor_name': donation.donor_name,
                'donor_contact': donation.donor_contact,
                'amount': donation.amount,
                'currency': donation.currency,
                'status': donation.status,
                'created_at': format_date(donation.created_at),
                'processed_at': format_date(donation.processed_at)
            })
        
        # Calculate collected amount
        collected = sum(donation.amount for donation in donations_query if donation.status == 'обработано')
        
        request_data = {
            'id': request_item.id,
            'unit_name': request_item.unit_name,
            'unit_type': request_item.unit_type,
            'location': request_item.location,
            'description': request_item.description,
            'needed_amount': request_item.needed_amount,
            'status': request_item.status,
            'created_at': format_date(request_item.created_at),
            'collected_amount': collected,
            'progress_percentage': min(100, int((collected / request_item.needed_amount) * 100)) if request_item.needed_amount > 0 else 0,
            'donations': donations
        }
        
        return jsonify({
            'success': True,
            'data': request_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting unit request: {str(e)}'}), 500

@admin_bp.route('/api/admin/unit-requests/<int:request_id>', methods=['PUT'])
@cross_origin()
@login_required()
@admin_required()
def update_unit_request(request_id):
    """Update unit request status and details"""
    try:
        request_item = UnitRequest.query.get(request_id)
        if not request_item:
            return jsonify({'success': False, 'message': 'Unit request not found'}), 404
        
        data = request.json
        
        # Update fields if provided
        if 'status' in data:
            old_status = request_item.status
            request_item.status = data['status']
            
            # Log status change
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Статус заявки изменен с '{old_status}' на '{data['status']}'",
                entity_type='unit_request',
                entity_id=request_id
            )
        
        if 'needed_amount' in data:
            old_amount = request_item.needed_amount
            request_item.needed_amount = data['needed_amount']
            
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Необходимая сумма изменена с {old_amount} ₽ на {data['needed_amount']} ₽",
                entity_type='unit_request',
                entity_id=request_id
            )
        
        if 'unit_name' in data:
            old_name = request_item.unit_name
            request_item.unit_name = data['unit_name']
            
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Название подразделения изменено с '{old_name}' на '{data['unit_name']}'",
                entity_type='unit_request',
                entity_id=request_id
            )
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Unit request updated successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating unit request: {str(e)}'}), 500