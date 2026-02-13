"""
Admin API endpoints for managing audit logs
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from sqlalchemy import or_, func
from datetime import datetime, timedelta

from backend.middleware import login_required, admin_required
from backend.config import Config
from backend.models import AdminUser, UnitRequest, Donation, AuditLog
admin_audit_bp = Blueprint('admin', __name__)

# Audit Logs Endpoints
@admin_audit_bp.route('/api/admin/audit-logs', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_audit_logs():
    """Get paginated list of audit logs"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        entity_type = request.args.get('entity_type', None, type=str)
        admin_id = request.args.get('admin_id', None, type=int)
        start_date = request.args.get('start_date', None, type=str)
        end_date = request.args.get('end_date', None, type=str)
        
        query = AuditLog.query
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        
        if admin_id:
            query = query.filter(AuditLog.admin_id == admin_id)
        
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        pagination = paginate_results(query, page, per_page)
        
        logs = []
        for log in pagination.items:
            logs.append({
                'id': log.id,
                'admin_id': log.admin_id,
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'created_at': format_date(log.created_at)
            })
        
        return jsonify({
            'success': True,
            'data': {
                'logs': logs,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting audit logs: {str(e)}'}), 500

@admin_audit_bp.route('/api/admin/audit-logs/<int:log_id>', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_audit_log(log_id):
    """Get detailed information about a specific audit log"""
    try:
        log = AuditLog.query.get(log_id)
        if not log:
            return jsonify({'success': False, 'message': 'Audit log not found'}), 404
        
        log_data = {
            'id': log.id,
            'admin_id': log.admin_id,
            'action': log.action,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'created_at': format_date(log.created_at),
            'admin_info': None
        }
        
        # Get admin information
        if log.admin_id:
            admin = AdminUser.query.get(log.admin_id)
            if admin:
                log_data['admin_info'] = {
                    'id': admin.id,
                    'username': admin.username,
                    'email': admin.email,
                    'role': admin.role
                }
        
        return jsonify({
            'success': True,
            'data': log_data
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting audit log: {str(e)}'}), 500

@admin_audit_bp.route('/api/admin/audit-logs/stats', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_audit_stats():
    """Get audit logs statistics"""
    try:
        # Audit logs by entity type
        entity_stats = db.session.query(
            AuditLog.entity_type,
            func.count(AuditLog.id)
        ).group_by(AuditLog.entity_type).all()
        
        # Audit logs by admin
        admin_stats = db.session.query(
            AuditLog.admin_id,
            func.count(AuditLog.id)
        ).group_by(AuditLog.admin_id).all()
        
        # Recent audit logs
        recent_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()
        
        # Prepare statistics
        stats = {
            'by_entity_type': {entity: count for entity, count in entity_stats},
            'by_admin': {admin_id: count for admin_id, count in admin_stats},
            'recent_logs': []
        }
        
        for log in recent_logs:
            stats['recent_logs'].append({
                'id': log.id,
                'admin_id': log.admin_id,
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'created_at': format_date(log.created_at)
            })
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting audit stats: {str(e)}'}), 500

@admin_audit_bp.route('/api/admin/audit-logs/export', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def export_audit_logs():
    """Export audit logs to CSV format"""
    try:
        # Get all logs for export
        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
        
        # Create CSV content
        csv_content = ['"ID","Admin ID","Action","Entity Type","Entity ID","Created At"']
        
        for log in logs:
            csv_content.append(f'"{log.id}","{log.admin_id}","{log.action}","{log.entity_type}","{log.entity_id}","{format_date(log.created_at)}"')
        
        csv_data = '\n'.join(csv_content)
        
        return jsonify({
            'success': True,
            'data': {
                'filename': f'audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv',
                'content': csv_data
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error exporting audit logs: {str(e)}'}), 500

@admin_audit_bp.route('/api/admin/audit-logs/clear', methods=['POST'])
@cross_origin()
@login_required()
@admin_required()
def clear_audit_logs():
    """Clear all audit logs"""
    try:
        # Delete all logs
        AuditLog.query.delete()
        db.session.commit()
        
        # Log the action
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action='Очищены все аудит-логи',
            entity_type='audit_log',
            entity_id=None
        )
        
        return jsonify({
            'success': True,
            'message': 'Audit logs cleared successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error clearing audit logs: {str(e)}'}), 500
