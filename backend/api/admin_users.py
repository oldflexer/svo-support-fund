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

admin_users_bp = Blueprint('admin', __name__)

# User Management Endpoints
@admin_users_bp.route('/api/admin/users', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_users():
    """Get paginated list of all users"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        search = request.args.get('search', None, type=str)
        role = request.args.get('role', None, type=str)
        
        query = AdminUser.query
        
        if search:
            query = query.filter(
                or_(
                    AdminUser.username.ilike(f"%{search}%")
                )
            )
        
        if role:
            query = query.filter(AdminUser.role == role)
        
        pagination = paginate_results(query, page, per_page)
        
        users = []
        for user in pagination.items:
            users.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'role': user.role,
                'created_at': format_date(user.created_at),
                'last_login': format_date(user.last_login),
                'is_active': user.is_active,
                'has_2fa': user.has_2fa,
                'two_factor_enabled': user.two_factor_enabled
            })
        
        return jsonify({
            'success': True,
            'data': {
                'users': users,
                'pagination': {
                    'page': pagination.page,
                    'per_page': pagination.per_page,
                    'total': pagination.total,
                    'pages': pagination.pages
                }
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting users: {str(e)}'}), 500

@admin_users_bp.route('/api/admin/users/<int:user_id>', methods=['GET'])
@cross_origin()
@login_required()
@admin_required()
def get_user(user_id):
    """Get detailed information about a specific user"""
    try:
        user = AdminUser.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404

        user_data = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active,
            'two_factor_enabled': user.two_factor_enabled,
            'created_at': format_date(user.created_at),
            'last_login': format_date(user.last_login),
            'login_attempts': user.login_attempts,
            'locked_until': format_date(user.locked_until),
            'audit_logs': []
        }

        # Get user audit logs
        audit_logs = AuditLog.query.filter_by(admin_id=user_id).order_by(AuditLog.created_at.desc()).limit(10).all()
        for log in audit_logs:
            user_data['audit_logs'].append({
                'id': log.id,
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'created_at': format_date(log.created_at)
            })
        
        return jsonify({
            'success': True,
            'data': user_data
        })

    except Exception as e:
        return jsonify({'success': False, 'message': f'Error getting user: {str(e)}'}), 500

@admin_users_bp.route('/api/admin/users', methods=['POST'])
@cross_origin()
@login_required()
@admin_required()
def create_user():
    """Create new admin user"""
    try:
        data = request.json

        # Validate required fields
        required_fields = ['username', 'email', 'password', 'role']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'message': f'Field {field} is required'}), 400

        # Check if username or email already exists
        if AdminUser.query.filter_by(username=data['username']).first():
            return jsonify({'success': False, 'message': 'Username already exists'}), 400

        if AdminUser.query.filter_by(email=data['email']).first():
            return jsonify({'success': False, 'message': 'Email already exists'}), 400

        # Create new user
        new_user = AdminUser(
            username=data['username'],
            email=data['email'],
            password=data['password'],
            role=data['role'],
            is_active=True,
            two_factor_enabled=False
        )

        db.session.add(new_user)
        db.session.commit()

        # Log audit
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action=f"Создан пользователь ''{data['username']}' с ролью '{data['role']}'",
            entity_type='user',
            entity_id=new_user.id
        )

        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'data': {
                'id': new_user.id,
                'username': new_user.username
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error creating user: {str(e)}'}), 500

@admin_users_bp.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@cross_origin()
@login_required()
@admin_required()
def update_user(user_id):
    """Update user details and permissions"""
    try:
        user = AdminUser.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        data = request.json
        
        # Update fields if provided
        changes = []
        
        if 'username' in data:
            old_username = user.username
            user.username = data['username']
            changes.append(f"Имя пользователя изменено с '{old_username}' на '{data['username']}'")
        
        if 'email' in data:
            old_email = user.email
            user.email = data['email']
            changes.append(f"Email изменен с '{old_email}' на '{data['email']}'")
        
        if 'role' in data:
            old_role = user.role
            user.role = data['role']
            changes.append(f"Роль изменена с '{old_role}' на '{data['role']}'")
        
        if 'is_active' in data:
            old_status = user.is_active
            user.is_active = data['is_active']
            changes.append(f"Статус активности изменен с '{old_status}' на '{data['is_active']}'")
        
        if 'two_factor_enabled' in data:
            old_2fa = user.two_factor_enabled
            user.two_factor_enabled = data['two_factor_enabled']
            changes.append(f"2FA изменен с '{old_2fa}' на '{data['two_factor_enabled']}'")
        
        if 'password' in data:
            user.password = data['password']
            changes.append('Пароль изменен')
        
        db.session.commit()
        
        # Log audit
        if changes:
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Изменен пользователь ''{user.username}': {', '.join(changes)}",
                entity_type='user',
                entity_id=user_id
            )
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error updating user: {str(e)}'}), 500

@admin_users_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@cross_origin()
@login_required()
@admin_required()
def delete_user(user_id):
    """Delete user"""
    try:
        user = AdminUser.query.get(user_id)
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Don't allow deletion of current user
        if user.id == current_app.config['current_user_id']:
            return jsonify({'success': False, 'message': 'Cannot delete current user'}), 400
        
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        # Log audit
        AuditLog.create_log(
            admin_id=current_app.config['current_user_id'],
            action=f"Удален пользователь ''{username}'",
            entity_type='user',
            entity_id=user_id
        )
        
        return jsonify({
            'success': True,
            'message': 'User deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting user: {str(e)}'}), 500

@admin_users_bp.route('/api/admin/users/bulk', methods=['PUT'])
@cross_origin()
@login_required()
@admin_required()
def bulk_update_users():
    """Bulk update multiple users"""
    try:
        data = request.json
        
        if 'user_ids' not in data or not isinstance(data['user_ids'], list):
            return jsonify({'success': False, 'message': 'user_ids array is required'}), 400
        
        updates = {}
        if 'is_active' in data:
            updates['is_active'] = data['is_active']
        if 'role' in data:
            updates['role'] = data['role']
        if 'two_factor_enabled' in data:
            updates['two_factor_enabled'] = data['two_factor_enabled']
        
        # Perform bulk update
        updated_count = AdminUser.query.filter(
            AdminUser.id.in_(data['user_ids'])
        ).update(updates, synchronize_session=False)
        
        db.session.commit()
        
        # Log audit for each updated user
        for user_id in data['user_ids']:
            change_details = []
            if 'is_active' in data:
                change_details.append(f"Статус активности изменен на ''{data['is_active']}'")
            if 'role' in data:
                change_details.append(f"Роль изменена на ''{data['role']}'")
            if 'two_factor_enabled' in data:
                change_details.append(f"2FA изменен на ''{data['two_factor_enabled']}'")
            
            AuditLog.create_log(
                admin_id=current_app.config['current_user_id'],
                action=f"Массовое обновление пользователей: {', '.join(change_details)}",
                entity_type='user',
                entity_id=user_id
            )
        
        return jsonify({
            'success': True,
            'message': f'{updated_count} users updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error bulk updating users: {str(e)}'}), 500
