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

@admin_bp.route('/api/admin/unit-requests', methods=['POST'])
@cross_origin()
@login_required()
@admin_required()
def create_unit_request():
    """Create new unit request"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['unit_name', 'unit_type', 'needed_amount', 'location', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'Field {field} is required'}), 400
        
        # Create new unit request
        new_request = UnitRequest(
            unit_name=data['unit_name'],
            unit_type=data['unit_type'],
            location=data['location'],
            description=data['description'],
            needed_amount=data['needed_amount'],
            urgency=data.get('urgency', 'средняя'),
            status='новая',
            created_by=current_app.config['current_user_id']
        )
        
        db.session.add(new_request)
        db.session.commit()
        
        # Log audit
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action=f"Создана заявка на поддержку подразделения ''{data['unit_name']}'",
            entity_type='unit_request',
            entity_id=new_request.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Unit request created successfully',
            'data': {
                'id': new_request.id,
                'unit_name': new_request.unit_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating unit request: {str(e)}'}), 500

@admin_bp.route('/api/admin/unit-requests/<int:request_id>', methods=['DELETE'])
@cross_origin()
@login_required()
@admin_required()
def delete_unit_request(request_id):
    """Delete unit request"""
    try:
        request_item = UnitRequest.query.get(request_id)
        if not request_item:
            return jsonify({'success': False, 'message': 'Unit request not found'}), 404
        
        # Check if request has donations
        donations = Donation.query.filter_by(unit_request_id=request_id).count()
        if donations > 0:
            return jsonify({'success': False, 'message': 'Cannot delete request with existing donations'}), 400
        
        unit_name = request_item.unit_name
        db.session.delete(request_item)
        db.session.commit()
        
        # Log audit
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action=f"Удалена заявка на поддержку подразделения ''{unit_name}'",
            entity_type='unit_request',
            entity_id=request_id
        )
        
        return jsonify({'success': True, 'message': 'Unit request deleted successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting unit request: {str(e)}'}), 500

@admin_bp.route('/api/admin/unit-requests/bulk', methods=['PUT'])
@cross_origin()
@login_required()
@admin_required()
def bulk_update_requests():
    """Bulk update multiple unit requests"""
    try:
        data = request.json
        
        if 'request_ids' not in data or not isinstance(data['request_ids'], list):
            return jsonify({'success': False, 'message': 'request_ids array is required'}), 400
        
        updates = {}
        if 'status' in data:
            updates['status'] = data['status']
        if 'urgency' in data:
            updates['urgency'] = data['urgency']
        
        # Perform bulk update
        updated_count = UnitRequest.query.filter(
            UnitRequest.id.in_(data['request_ids'])
        ).update(updates, synchronize_session=False)
        
        db.session.commit()
        
        # Log audit for each updated request
        for request_id in data['request_ids']:
            change_details = []
            if 'status' in data:
                change_details.append(f"Статус изменен на ''{data['status']}'")
            if 'urgency' in data:
                change_details.append(f"Уровень срочности изменен на ''{data['urgency']}'")
            
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Массовое обновление заявок: {', '.join(change_details)}",
                entity_type='unit_request',
                entity_id=request_id
            )
        
        return jsonify({
            'success': True,
            'message': f'{updated_count} unit requests updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error bulk updating requests: {str(e)}'}), 500
