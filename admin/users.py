from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User
from forms import UserForm
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: Admin users
# -------------------------------

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@role_required('admin')
def get_users():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    pagination = User.query.order_by(User.created_at.asc()).paginate(page=page, per_page=per_page, error_out=False)

    users_data = [{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'full_name': u.full_name,
        'role': u.role,
        'is_active': u.is_active,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'last_login': u.last_login.isoformat() if u.last_login else None,
        'two_factor_enabled': u.two_factor_enabled
    } for u in pagination.items]

    return jsonify({
        'items': users_data,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@admin_bp.route('/users', methods=['POST'])
@jwt_required()
@role_required('admin')
def create_user():
    data = request.get_json() or {}
    form = UserForm(data=data)

    # required = ['username', 'email', 'password', 'role']
    # for field in required:
    #     if field not in data:
    #         return jsonify({'error': f'Поле {field} обязательно'}), 400
    
    if User.query.filter_by(username=form.username.data).first():
        return jsonify({'error': 'Логин уже занят'}), 400
    if User.query.filter_by(email=form.email.data).first():
        return jsonify({'error': 'Email уже занят'}), 400
    
    user = User(
        username=form.username.data,
        email=form.email.data,
        full_name=form.full_name.data or '',
        role=form.role.data,
        is_active=form.is_active.data
    )
    user.set_password(form.password.data)

    db.session.add(user)
    db.session.commit()
    
    log_action(get_jwt_identity(), 'create_user', f'Создан пользователь {user.id}', request.remote_addr)
    
    return jsonify({'message': 'Пользователь создан', 'id': user.id}), 201

@admin_bp.route('/users/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin')
def update_user(id):
    user = User.query.get_or_404(id)
    data = request.get_json() or {}
    
    # Update fields
    if 'username' in data and data['username'] != user.username:
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Логин уже занят'}), 400
        user.username = data['username']

    if 'email' in data and data['email'] != user.email:
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email уже занят'}), 400
        user.email = data['email']

    if 'email' in data:
        user.email = data['email']

    if 'full_name' in data:
        user.full_name = data['full_name']

    if 'role' in data:
        user.role = data['role']

    if 'is_active' in data:
        user.is_active = data['is_active']

    if 'password' in data and data['password']:
        user.set_password(data['password'])

    db.session.commit()
    
    log_action(get_jwt_identity(), 'update_user', f'Обновлен пользователь {user.id}', request.remote_addr)
    
    return jsonify({'message': 'Пользователь обновлен'}), 200

@admin_bp.route('/users/<int:id>/toggle', methods=['POST'])
@jwt_required()
@role_required('admin')
def toggle_user(id):
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(id)

    if user.id == current_user_id:
        return jsonify({'error': 'Нельзя изменить статус самого себя'}), 400
    
    user.is_active = not user.is_active
    db.session.commit()
    action = 'активирован' if user.is_active else 'деактивирован'

    log_action(get_jwt_identity(), 'toggle_user', f'Пользователь {user.id} {action}', request.remote_addr)
    
    return jsonify({'message': f'Пользователь {action}', 'is_active': user.is_active}), 200

@admin_bp.route('/users/<int:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin')
def delete_user(id):
    """
    Удаление пользователя по ID.
    """
    user = User.query.get(id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    current_user_id = get_jwt_identity()
    if user.id == current_user_id:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400

    db.session.delete(user)
    db.session.commit()

    log_action(get_jwt_identity(), 'delete_user', f'Удалён пользователь {id}', request.remote_addr)

    return jsonify({'message': 'Пользователь успешно удалён'}), 200
