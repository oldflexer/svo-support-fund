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

admin_donations_bp = Blueprint('admin', __name__)

# Donations Endpoints
@admin_donations_bp.route('/api/admin/donations', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_donations():
    """Get paginated list of all donations"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status = request.args.get('status', None, type=str)
        unit_request_id = request.args.get('unit_request_id', None, type=int)
        donor_name = request.args.get('donor_name', None, type=str)
        
        query = Donation.query
        
        if status:
            query = query.filter(Donation.status == status)
        
        if unit_request_id:
            query = query.filter(Donation.unit_request_id == unit_request_id)
        
        if donor_name:
            query = query.filter(
                Donation.donor_name.ilike(f"%{donor_name}%")
            )
        
        pagination = paginate_results(query, page, per_page)
        
        donations = []
        for donation in pagination.items:
            donations.append({
                'id': donation.id,
                'donor_name': donation.donor_name,
                'donor_contact': donation.donor_contact,
                'unit_request_id': donation.unit_request_id,
                'amount': donation.amount,
                'currency': donation.currency,
                'status': donation.status,
                'created_at': format_date(donation.created_at),
                'processed_at': format_date(donation.processed_at),
                'notes': donation.notes
            })
        
        return jsonify({
            'success': True,
            'data': {
                'donations': donations,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting donations: {str(e)}'}), 500

@admin_donations_bp.route('/api/admin/donations/<int:donation_id>', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_donation(donation_id):
    """Get detailed information about a specific donation"""
    try:
        donation = Donation.query.get(donation_id)
        if not donation:
            return jsonify({'success': False, 'message': 'Donation not found'}), 404
        
        donation_data = {
            'id': donation.id,
            'donor_name': donation.donor_name,
            'donor_contact': donation.donor_contact,
            'unit_request_id': donation.unit_request_id,
            'amount': donation.amount,
            'currency': donation.currency,
            'status': donation.status,
            'created_at': format_date(donation.created_at),
            'processed_at': format_date(donation.processed_at),
            'notes': donation.notes,
            'unit_request': None
        }
        
        # Get related unit request
        if donation.unit_request_id:
            unit_request = UnitRequest.query.get(donation.unit_request_id)
            if unit_request:
                donation_data['unit_request'] = {
                    'id': unit_request.id,
                    'unit_name': unit_request.unit_name,
                    'unit_type': unit_request.unit_type,
                    'location': unit_request.location
                }
        
        return jsonify({
            'success': True,
            'data': donation_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting donation: {str(e)}'}), 500

@admin_donations_bp.route('/api/admin/donations', methods=['POST'])
@cross_origin()
@login_required()
@admin_required()
def create_donation():
    """Create new donation"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['donor_name', 'donor_contact', 'unit_request_id', 'amount']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'Field {field} is required'}), 400
        
        # Validate unit request exists
        if not UnitRequest.query.get(data['unit_request_id']):
            return jsonify({'success': False, 'message': 'Unit request not found'}), 404
        
        # Create new donation
        new_donation = Donation(
            donor_name=data['donor_name'],
            donor_contact=data['donor_contact'],
            unit_request_id=data['unit_request_id'],
            amount=data['amount'],
            currency=data.get('currency', 'RUB'),
            status='новое',
            notes=data.get('notes', ''),
            created_by=current_app.config['current_user_id']
        )
        
        db.session.add(new_donation)
        db.session.commit()
        
        # Log audit
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action=f"Создано пожертвование от ''{data['donor_name']}' на сумму {data['amount']} ₽",
            entity_type='donation',
            entity_id=new_donation.id
        )
        
        return jsonify({
            'success': True,
            'message': 'Donation created successfully',
            'data': {
                'id': new_donation.id,
                'donor_name': new_donation.donor_name
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating donation: {str(e)}'}), 500

@admin_donations_bp.route('/api/admin/donations/<int:donation_id>', methods=['PUT'])
@cross_origin()
@login_required()
@admin_required()
def update_donation(donation_id):
    """Update donation status and details"""
    try:
        donation = Donation.query.get(donation_id)
        if not donation:
            return jsonify({'success': False, 'message': 'Donation not found'}), 404
        
        data = request.json
        
        # Update fields if provided
        changes = []
        
        if 'status' in data:
            old_status = donation.status
            donation.status = data['status']
            changes.append(f"Статус изменен с '{old_status}' на '{data['status']}'")
            
            if data['status'] == 'обработано':
                donation.processed_at = datetime.now()
        
        if 'notes' in data:
            old_notes = donation.notes
            donation.notes = data['notes']
            changes.append(f"Примечания изменены с '{old_notes}' на '{data['notes']}'")
        
        db.session.commit()
        
        # Log audit
        if changes:
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Изменено пожертвование ''{donation.id}': {', '.join(changes)}",
                entity_type='donation',
                entity_id=donation_id
            )
        
        return jsonify({
            'success': True,
            'message': 'Donation updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating donation: {str(e)}'}), 500

@admin_donations_bp.route('/api/admin/donations/<int:donation_id>', methods=['DELETE'])
@cross_origin()
@login_required()
@admin_required()
def delete_donation(donation_id):
    """Delete donation"""
    try:
        donation = Donation.query.get(donation_id)
        if not donation:
            return jsonify({'success': False, 'message': 'Donation not found'}), 404
        
        donor_name = donation.donor_name
        db.session.delete(donation)
        db.session.commit()
        
        # Log audit
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action=f"Удалено пожертвование от ''{donor_name}'",
            entity_type='donation',
            entity_id=donation_id
        )
        
        return jsonify({
            'success': True,
            'message': 'Donation deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting donation: {str(e)}'}), 500

@admin_donations_bp.route('/api/admin/donations/bulk', methods=['PUT'])
@cross_origin()
@login_required()
@admin_required()
def bulk_update_donations():
    """Bulk update multiple donations"""
    try:
        data = request.json
        
        if 'donation_ids' not in data or not isinstance(data['donation_ids'], list):
            return jsonify({'success': False, 'message': 'donation_ids array is required'}), 400
        
        updates = {}
        if 'status' in data:
            updates['status'] = data['status']
        if 'notes' in data:
            updates['notes'] = data['notes']
        
        # Perform bulk update
        updated_count = Donation.query.filter(
            Donation.id.in_(data['donation_ids'])
        ).update(updates, synchronize_session=False)
        
        db.session.commit()
        
        # Log audit for each updated donation
        for donation_id in data['donation_ids']:
            change_details = []
            if 'status' in data:
                change_details.append(f"Статус изменен на ''{data['status']}'")
            if 'notes' in data:
                change_details.append(f"Примечания изменены на ''{data['notes']}'")
            
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Массовое обновление пожертвований: {', '.join(change_details)}",
                entity_type='donation',
                entity_id=donation_id
            )
        
        return jsonify({
            'success': True,
            'message': f'{updated_count} donations updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error bulk updating donations: {str(e)}'}), 500

@admin_donations_bp.route('/api/admin/donations/stats', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_donations_stats():
    """Get donations statistics"""
    try:
        # Total donations
        total_donations = db.session.query(
            func.count(Donation.id),
            func.sum(Donation.amount)
        ).filter(
            Donation.status == 'обработано'
        ).first()
        
        # Donations by status
        status_stats = db.session.query(
            Donation.status,
            func.count(Donation.id)
        ).group_by(Donation.status).all()
        
        # Recent donations
        recent_donations = Donation.query.filter(
            Donation.status == 'обработано'
        ).order_by(Donation.created_at.desc()).limit(5).all()
        
        # Prepare statistics
        stats = {
            'total_count': total_donations[0] or 0,
            'total_amount': total_donations[1] or 0,
            'by_status': {status: count for status, count in status_stats},
            'recent_donations': []
        }
        
        for donation in recent_donations:
            stats['recent_donations'].append({
                'id': donation.id,
                'donor_name': donation.donor_name,
                'amount': donation.amount,
                'currency': donation.currency,
                'created_at': format_date(donation.created_at)
            })
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting donations stats: {str(e)}'}), 500
