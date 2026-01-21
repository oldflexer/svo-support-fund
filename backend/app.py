from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
from schemas import validate_request, validate_request_data, SCHEMAS
from marshmallow import ValidationError
from middleware import validate_json, validate_query_params
from models import db, bcrypt, AdminUser, Fighter, AssistanceType, Donation, Volunteer, Delivery, AuditLog, EquipmentRequest
from two_factor import TwoFactorAuth, require_2fa_setup, require_2fa_enabled
from config import Config
from auth import (
    create_access_token, create_refresh_token, verify_token,
    login_required, role_required, log_audit, validate_password,
    AuthError
)
from datetime import datetime, timedelta
import json
import os

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, supports_credentials=True)
db.init_app(app)
bcrypt.init_app(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Создание директории для загрузок
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация базы данных с тестовыми данными
def init_db():
    with app.app_context():
        db.create_all()
        
        # Создаём администратора по умолчанию если нет
        if AdminUser.query.count() == 0:
            admin = AdminUser(
                username='admin',
                email='admin@zaschitnikam.ru',
                full_name='Главный администратор',
                role='admin',
                is_active=True
            )
            admin.set_password('Admin123!')
            db.session.add(admin)
            
            # Создаём тестового модератора
            moderator = AdminUser(
                username='moderator',
                email='moderator@zaschitnikam.ru',
                full_name='Модератор',
                role='moderator',
                is_active=True
            )
            moderator.set_password('Moderator123!')
            db.session.add(moderator)
        
        # Добавляем типы помощи если их нет
        if AssistanceType.query.count() == 0:
            assistance_types = [
                AssistanceType(
                    name="Медицинские расходные материалы",
                    description="Бинты, жгуты, аптечки, медикаменты",
                    icon="fa-first-aid",
                    category="медицина"
                ),
                AssistanceType(
                    name="Тепловизионные прицелы",
                    description="Тепловизоры и ПНВ для ночных операций",
                    icon="fa-binoculars",
                    category="техника"
                ),
                AssistanceType(
                    name="Бронежилеты и каски",
                    description="Средства индивидуальной защиты",
                    icon="fa-shield-alt",
                    category="снаряжение"
                ),
                AssistanceType(
                    name="Дроны",
                    description="БПЛА для разведки и корректировки",
                    icon="fa-drone",
                    category="техника"
                ),
                AssistanceType(
                    name="Тёплая одежда",
                    description="Термобельё, зимние куртки, обувь",
                    icon="fa-tshirt",
                    category="снаряжение"
                ),
                AssistanceType(
                    name="Питание и вода",
                    description="Сухпайки, готовая еда, вода",
                    icon="fa-utensils",
                    category="прочее"
                ),
                AssistanceType(
                    name="Средства связи",
                    description="Рации, спутниковые телефоны",
                    icon="fa-satellite-dish",
                    category="техника"
                ),
                AssistanceType(
                    name="Финансовая помощь семьям",
                    description="Помощь семьям погибших и раненых",
                    icon="fa-hand-holding-usd",
                    category="прочее"
                )
            ]
            db.session.add_all(assistance_types)
        
        # Добавляем тестовых бойцов если их нет
        if Fighter.query.count() == 0:
            fighters = [
                Fighter(
                    call_sign="Волк",
                    unit="7-я гвардейская десантно-штурмовая дивизия",
                    region="Донецкая область",
                    status="активный",
                    needs=json.dumps([
                        "Тепловизор Armasight",
                        "Бронепластины 6 класса",
                        "Зимнее термобельё"
                    ]),
                    story="Служит с первого дня СВО. Прошёл несколько горячих точек. Нуждается в современном оборудовании для выполнения задач.",
                    photo_url="https://images.unsplash.com/photo-1618331833071-1c0c6ee3d19e?w=400",
                    is_verified=True,
                    priority=1
                ),
                Fighter(
                    call_sign="Медведь",
                    unit="150-я мотострелковая дивизия",
                    region="Запорожская область",
                    status="ранен",
                    needs=json.dumps([
                        "Реабилитационные средства",
                        "Лекарства для восстановления",
                        "Специализированное питание"
                    ]),
                    story="Получил ранение при выполнении боевой задачи. Проходит лечение в госпитале. Нуждается в поддержке для восстановления.",
                    photo_url="https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=400",
                    is_verified=True,
                    priority=1
                ),
                Fighter(
                    call_sign="Сокол",
                    unit="Бригада морской пехоты",
                    region="Херсонская область",
                    status="активный",
                    needs=json.dumps([
                        "Спутниковый телефон Iridium",
                        "Тактический дрон DJI Mavic",
                        "Ночной прицел"
                    ]),
                    story="Выполняет задачи по разведке и корректировке огня. Требуется специальное оборудование для повышения эффективности.",
                    is_verified=True,
                    priority=2
                ),
                Fighter(
                    call_sign="Тигр",
                    unit="Отдельная мотострелковая бригада",
                    region="Луганская область",
                    status="активный",
                    needs=json.dumps([
                        "Новая обувь зимняя 45 размер",
                        "Перчатки тактические",
                        "Палатка армейская"
                    ]),
                    story="Находится на передовой более 8 месяцев. Основное снаряжение износилось, требуется замена.",
                    is_verified=True,
                    priority=2
                )
            ]
            db.session.add_all(fighters)
            db.session.commit()

@app.route('/')
def index():
    return jsonify({
        "message": "API Фонда поддержки участников СВО",
        "version": "1.0",
        "auth_required_endpoints": [
            "/api/admin/* - админ панель",
            "/api/auth/refresh - обновление токена",
            "/api/auth/logout - выход"
        ],
        "endpoints": [
            "/api/fighters - список бойцов",
            "/api/assistance/types - типы помощи",
            "/api/stats - статистика",
            "/api/donate - сделать пожертвование",
            "/api/volunteer - стать волонтером"
        ]
    })

# API эндпоинты
@app.route('/api/fighters', methods=['GET'])
def get_fighters():
    """Получить список бойцов с фильтрацией"""
    status = request.args.get('status')
    priority = request.args.get('priority')
    verified = request.args.get('verified', 'true').lower() == 'true'
    
    query = Fighter.query
    
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=int(priority))
    if verified:
        query = query.filter_by(is_verified=True)
    
    fighters = query.order_by(Fighter.priority, Fighter.created_at.desc()).all()
    
    return jsonify([{
        'id': f.id,
        'call_sign': f.call_sign,
        'unit': f.unit,
        'region': f.region,
        'status': f.status,
        'needs': json.loads(f.needs) if f.needs else [],
        'story': f.story,
        'photo_url': f.photo_url,
        'is_verified': f.is_verified,
        'priority': f.priority,
        'priority_label': {1: 'Высокий', 2: 'Средний', 3: 'Низкий'}.get(f.priority, 'Не указан'),
        'status_class': {
            'активный': 'status-active',
            'ранен': 'status-wounded',
            'на лечении': 'status-treatment',
            'отпуск': 'status-leave'
        }.get(f.status, 'status-default'),
        'created_at': f.created_at.strftime('%d.%m.%Y')
    } for f in fighters])

@app.route('/api/fighters/<int:fighter_id>', methods=['GET'])
def get_fighter(fighter_id):
    """Получить детальную информацию о бойце"""
    fighter = Fighter.query.get_or_404(fighter_id)
    
    # Получаем связанные пожертвования
    donations = Donation.query.filter_by(fighter_id=fighter_id).order_by(Donation.created_at.desc()).limit(10).all()
    
    return jsonify({
        'fighter': {
            'id': fighter.id,
            'call_sign': fighter.call_sign,
            'unit': fighter.unit,
            'region': fighter.region,
            'status': fighter.status,
            'needs': json.loads(fighter.needs) if fighter.needs else [],
            'story': fighter.story,
            'photo_url': fighter.photo_url,
            'is_verified': fighter.is_verified,
            'priority': fighter.priority,
            'created_at': fighter.created_at.strftime('%d.%m.%Y')
        },
        'donations': [{
            'amount': d.amount,
            'donor_name': 'Аноним' if d.is_anonymous else d.donor_name,
            'message': d.message,
            'created_at': d.created_at.strftime('%d.%m.%Y %H:%M')
        } for d in donations]
    })

@app.route('/api/assistance/types', methods=['GET'])
def get_assistance_types():
    """Получить типы помощи"""
    category = request.args.get('category')
    
    query = AssistanceType.query
    if category:
        query = query.filter_by(category=category)
    
    types = query.order_by(AssistanceType.category).all()
    
    return jsonify([{
        'id': t.id,
        'name': t.name,
        'description': t.description,
        'icon': t.icon,
        'category': t.category,
        'category_ru': {
            'медицина': 'Медицинская помощь',
            'техника': 'Техника и оборудование',
            'снаряжение': 'Снаряжение',
            'прочее': 'Прочая помощь'
        }.get(t.category, t.category)
    } for t in types])

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Получить статистику фонда"""
    total_fighters = Fighter.query.count()
    total_verified = Fighter.query.filter_by(is_verified=True).count()
    active_fighters = Fighter.query.filter_by(status='активный').count()
    wounded_fighters = Fighter.query.filter_by(status='ранен').count()
    
    # Сумма пожертвований
    total_donated = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    
    # Последние пожертвования
    recent_donations = Donation.query.order_by(Donation.created_at.desc()).limit(5).all()
    
    # Волонтеры
    total_volunteers = Volunteer.query.filter_by(is_active=True).count()
    
    # Активные запросы на снаряжение
    active_requests = EquipmentRequest.query.filter_by(status='требуется').count()
    
    return jsonify({
        'total_fighters': total_fighters,
        'total_verified': total_verified,
        'active_fighters': active_fighters,
        'wounded_fighters': wounded_fighters,
        'total_donated': total_donated,
        'total_volunteers': total_volunteers,
        'active_requests': active_requests,
        'recent_donations': [{
            'amount': d.amount,
            'donor_name': 'Аноним' if d.is_anonymous else d.donor_name,
            'created_at': d.created_at.strftime('%d.%m.%Y')
        } for d in recent_donations]
    })

@app.route('/api/donate', methods=['POST'])
def create_donation():
    """Создать пожертвование"""
    try:
        validated_data = validate_request_data('donation_create', request.json)
        
        # Проверяем сумму
        if validated_data['amount'] < 100:
            return jsonify({
                'success': False,
                'message': 'Минимальная сумма пожертвования - 100 рублей'
            }), 400
        
        donation = Donation(
            donor_name=validated_data['name'],
            amount=validated_data['amount'],
            fighter_id=validated_data.get('fighter_id'),
            assistance_type_id=validated_data.get('assistance_type_id'),
            message=validated_data['message'],
            is_anonymous=validated_data['is_anonymous'],
            status='ожидает'
        )
        
        db.session.add(donation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Спасибо за вашу поддержку участников СВО!',
            'donation_id': donation.id,
            'receipt_number': f"DON-{donation.id:06d}"
        })
        
    except ValidationError as err:
        return jsonify({
            'success': False,
            'message': 'Ошибка валидации данных пожертвования',
            'errors': err.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/volunteer/register', methods=['POST'])
def register_volunteer():
    """Зарегистрироваться как волонтер"""
    try:
        validated_data = validate_request_data('volunteer_create', request.json)
        
        volunteer = Volunteer(
            name=validated_data['name'],
            email=validated_data['email'],
            phone=validated_data['phone'],
            skills=validated_data['skills'],
            city=validated_data['city'],
            can_deliver=validated_data['can_deliver'],
            is_active=True
        )
        
        db.session.add(volunteer)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Спасибо за готовность помочь! Мы свяжемся с вами в ближайшее время.',
            'volunteer_id': volunteer.id
        })
    
    except ValidationError as err:
        return jsonify({
            'success': False,
            'message': 'Ошибка валидации данных волонтёра',
            'errors': err.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/equipment/request', methods=['POST'])
def create_equipment_request():
    """Создать запрос на снаряжение"""
    data = request.json
    
    request_item = EquipmentRequest(
        fighter_id=data['fighter_id'],
        item_name=data['item_name'],
        quantity=data.get('quantity', 1),
        urgency=data.get('urgency', 'обычно'),
        status='требуется'
    )
    
    try:
        db.session.add(request_item)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Запрос на снаряжение создан',
            'request_id': request_item.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/needs/urgent', methods=['GET'])
def get_urgent_needs():
    """Получить срочные потребности"""
    urgent_fighters = Fighter.query.filter_by(priority=1).filter_by(is_verified=True).all()
    
    needs = []
    for fighter in urgent_fighters:
        if fighter.needs:
            fighter_needs = json.loads(fighter.needs)
            for need in fighter_needs:
                needs.append({
                    'fighter_call_sign': fighter.call_sign,
                    'need': need,
                    'fighter_id': fighter.id,
                    'status': fighter.status,
                    'region': fighter.region
                })
    
    return jsonify(needs[:10])  # Ограничиваем 10 срочными потребностями

@app.route('/api/deliveries/planned', methods=['GET'])
def get_planned_deliveries():
    """Получить запланированные доставки"""
    deliveries = Delivery.query.filter(Delivery.status.in_(['планируется', 'в пути'])).all()
    
    return jsonify([{
        'id': d.id,
        'destination': d.destination,
        'status': d.status,
        'departure_date': d.departure_date.strftime('%d.%m.%Y') if d.departure_date else None,
        'estimated_arrival': d.estimated_arrival.strftime('%d.%m.%Y') if d.estimated_arrival else None
    } for d in deliveries])

# ==================== AUTH ROUTES ====================

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("5 per minute")
@validate_json('login')
def login():
    """Авторизация администратора"""
    #data = request.json
    try:
        # Валидируем данные
        #validated_data = validate_request_data('login', request.json)
        data = request.validated_data

        # Проверяем лимит попыток
        allowed, wait_time = TwoFactorAuth.check_rate_limit(
            data['username'], 
            request.remote_addr
        )
        
        if not allowed:
            return jsonify({
                'success': False,
                'message': f'Слишком много попыток. Попробуйте через {wait_time} секунд.',
                'wait_time': wait_time
            }), 429

        # Используем валидированные данные
        # Ищем пользователя
        user = AdminUser.query.filter_by(username=data['username']).first()
        if not user:
            TwoFactorAuth.record_failed_attempt(data['username'], reason='user_not_found')
            return jsonify({
                'success': False,
                'message': 'Invalid credentials'
            }), 401
        
        # Проверяем пароль
        if not user.check_password(data['password']):
            TwoFactorAuth.record_failed_attempt(
                data['username'], 
                user.id, 
                reason='wrong_password'
            )
            return jsonify({
                'success': False,
                'message': 'Invalid credentials'
            }), 401
        
        # Проверяем активность
        if not user.is_active:
            TwoFactorAuth.record_failed_attempt(
                data['username'], 
                user.id, 
                reason='account_disabled'
            )
            return jsonify({
                'success': False,
                'message': 'Account is disabled'
            }), 403
        
        # Если 2FA включена, возвращаем временный токен
        if user.two_factor_enabled:
            # Создаём временный токен для 2FA
            temp_token = jwt.encode({
                'exp': datetime.utcnow() + timedelta(minutes=5),
                'iat': datetime.utcnow(),
                'sub': user.id,
                'type': 'temp_2fa',
                'username': user.username
            }, app.config['JWT_SECRET_KEY'], algorithm='HS256')
            
            # Логируем успешный ввод пароля
            log_audit('login_password_ok', 'user', user.id, 'Password correct, 2FA required')
            
            return jsonify({
                'success': True,
                'message': 'Требуется двухфакторная аутентификация',
                'two_factor_required': True,
                'temp_token': temp_token,
                'user_id': user.id,
                'username': user.username
            })
        
        # Если 2FA не включена, создаём обычные токены
        # Обновляем время последнего входа
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Создаём токены
        access_token = create_access_token(user.id, user.username, user.role)
        refresh_token = create_refresh_token(user.id)
        
        # Очищаем неудачные попытки
        TwoFactorAuth.clear_failed_attempts(user.username)
        
        # Логируем успешный вход
        log_audit('login', 'user', user.id, 'Logged in without 2FA')
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict(),
            'two_factor_required': False
        })
    
    except ValidationError as err:
        return jsonify({
            'success': False,
            'message': 'Ошибка валидации',
            'errors': err.messages
        }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login error: {str(e)}'
        }), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Обновление access токена"""
    try:
        data = request.json
        if not data or not data.get('refresh_token'):
            return jsonify({
                'success': False,
                'message': 'Refresh token required'
            }), 400
        
        # Верифицируем refresh токен
        payload = verify_token(data['refresh_token'])
        
        if payload.get('type') != 'refresh':
            return jsonify({
                'success': False,
                'message': 'Invalid token type'
            }), 400
        
        # Получаем пользователя
        user = AdminUser.query.get(payload['sub'])
        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'message': 'User not found or inactive'
            }), 401
        
        # Создаём новый access токен
        new_access_token = create_access_token(user.id, user.username, user.role)
        
        return jsonify({
            'success': True,
            'access_token': new_access_token
        })
        
    except AuthError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 401
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Token refresh error: {str(e)}'
        }), 500

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Выход из системы"""
    log_audit('logout')
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })

@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Получение информации о текущем пользователе"""
    return jsonify({
        'success': True,
        'user': request.current_user.to_dict()
    })

# ==================== ADMIN ROUTES ====================

# Управление администраторами
@app.route('/api/admin/users', methods=['GET'])
@role_required('admin')
def get_admin_users():
    """Получить список администраторов"""
    users = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
    return jsonify({
        'success': True,
        'users': [user.to_dict() for user in users]
    })

@app.route('/api/admin/users', methods=['POST'])
@role_required('admin')
@validate_request('admin_create')
def create_admin_user():
    """Создать нового администратора"""
    # Данные уже валидированы и доступны в request.validated_data
    data = request.validated_data
    
    # Проверяем уникальность
    if AdminUser.query.filter_by(username=data['username']).first():
        return jsonify({
            'success': False,
            'message': 'Username already exists'
        }), 400
    
    try:
        user = AdminUser(
            username=data['username'],
            email=data['email'],
            full_name=data.get('full_name', ''),
            role=data.get('role', 'moderator'),
            is_active=data.get('is_active', True)
        )
        user.set_password(data['password'])
        
        db.session.add(user)
        db.session.commit()
        
        log_audit('create', 'user', user.id, f'Created user {user.username}')
        
        return jsonify({
            'success': True,
            'message': 'User created successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error creating user: {str(e)}'
        }), 500

@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@role_required('admin')
def update_admin_user(user_id):
    """Обновить администратора"""
    data = request.json
    
    user = AdminUser.query.get_or_404(user_id)
    
    # Нельзя редактировать самого себя
    if user.id == request.current_user.id and 'role' in data:
        return jsonify({
            'success': False,
            'message': 'Cannot change your own role'
        }), 400
    
    try:
        if 'username' in data and data['username'] != user.username:
            if AdminUser.query.filter_by(username=data['username']).first():
                return jsonify({
                    'success': False,
                    'message': 'Username already exists'
                }), 400
            user.username = data['username']
        
        if 'email' in data and data['email'] != user.email:
            if AdminUser.query.filter_by(email=data['email']).first():
                return jsonify({
                    'success': False,
                    'message': 'Email already exists'
                }), 400
            user.email = data['email']
        
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        if 'role' in data:
            user.role = data['role']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'password' in data and data['password']:
            is_valid, msg = validate_password(data['password'])
            if not is_valid:
                return jsonify({
                    'success': False,
                    'message': msg
                }), 400
            user.set_password(data['password'])
        
        db.session.commit()
        
        log_audit('update', 'user', user.id, f'Updated user {user.username}')
        
        return jsonify({
            'success': True,
            'message': 'User updated successfully',
            'user': user.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating user: {str(e)}'
        }), 500

# Управление бойцами (защищённые версии)
@app.route('/api/admin/fighters', methods=['GET'])
@login_required
@validate_query_params('fighter_list')  # Валидация query параметров
def admin_get_fighters():
    """Получить всех бойцов (для админки)"""
    # Параметры уже валидированы
    params = request.validated_query
    
    page = params.get('page', 1)
    per_page = params.get('per_page', 20)
    status = params.get('status')
    
    fighters = Fighter.query.order_by(Fighter.created_at.desc()).all()
    return jsonify({
        'success': True,
        'fighters': [{
            'id': f.id,
            'call_sign': f.call_sign,
            'unit': f.unit,
            'region': f.region,
            'status': f.status,
            'needs': json.loads(f.needs) if f.needs else [],
            'story': f.story,
            'photo_url': f.photo_url,
            'is_verified': f.is_verified,
            'priority': f.priority,
            'created_at': f.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for f in fighters]
    })

@app.route('/api/admin/fighters', methods=['POST'])
@role_required('admin', 'moderator')
def admin_create_fighter():
    """Создать нового бойца"""
    try:
        validated_data  = validate_request_data('fighter_create', request.json)
        
        fighter = Fighter(
            call_sign=validated_data['call_sign'],
            unit=validated_data['unit'],
            region=validated_data['region'],
            status=validated_data['status'],
            needs=json.dumps(validated_data['needs']),
            story=validated_data['story'],
            photo_url=validated_data['photo_url'],
            is_verified=validated_data['is_verified'],
            priority=validated_data['priority']
        )
        
        db.session.add(fighter)
        db.session.commit()
        
        log_audit('create', 'fighter', fighter.id, f'Created fighter {fighter.call_sign}')
        
        return jsonify({
            'success': True,
            'message': 'Fighter created successfully',
            'fighter': {
                'id': fighter.id,
                'call_sign': fighter.call_sign
            }
        })
    
    except ValidationError as err:
        return jsonify({
            'success': False,
            'message': 'Ошибка валидации данных бойца',
            'errors': err.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error creating fighter: {str(e)}'
        }), 500

@app.route('/api/admin/fighters/<int:fighter_id>', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_update_fighter(fighter_id):
    """Обновить бойца"""
    data = request.json
    
    fighter = Fighter.query.get_or_404(fighter_id)
    
    try:
        if 'call_sign' in data:
            fighter.call_sign = data['call_sign']
        if 'unit' in data:
            fighter.unit = data['unit']
        if 'region' in data:
            fighter.region = data['region']
        if 'status' in data:
            fighter.status = data['status']
        if 'needs' in data:
            fighter.needs = json.dumps(data['needs'])
        if 'story' in data:
            fighter.story = data['story']
        if 'photo_url' in data:
            fighter.photo_url = data['photo_url']
        if 'is_verified' in data:
            fighter.is_verified = data['is_verified']
        if 'priority' in data:
            fighter.priority = data['priority']
        
        db.session.commit()
        
        log_audit('update', 'fighter', fighter.id, f'Updated fighter {fighter.call_sign}')
        
        return jsonify({
            'success': True,
            'message': 'Fighter updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating fighter: {str(e)}'
        }), 500

@app.route('/api/admin/fighters/<int:fighter_id>', methods=['DELETE'])
@role_required('admin')
def admin_delete_fighter(fighter_id):
    """Удалить бойца"""
    fighter = Fighter.query.get_or_404(fighter_id)
    
    try:
        db.session.delete(fighter)
        db.session.commit()
        
        log_audit('delete', 'fighter', fighter_id, f'Deleted fighter {fighter.call_sign}')
        
        return jsonify({
            'success': True,
            'message': 'Fighter deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error deleting fighter: {str(e)}'
        }), 500

# Управление пожертвованиями
@app.route('/api/admin/donations', methods=['GET'])
@login_required
def admin_get_donations():
    """Получить все пожертвования"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status = request.args.get('status')
    
    query = Donation.query
    
    if status:
        query = query.filter_by(status=status)
    
    donations = query.order_by(Donation.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'donations': [{
            'id': d.id,
            'donor_name': d.donor_name,
            'amount': d.amount,
            'fighter_id': d.fighter_id,
            'fighter_call_sign': d.fighter.call_sign if d.fighter else None,
            'assistance_type': d.assistance_type.name if d.assistance_type else None,
            'message': d.message,
            'is_anonymous': d.is_anonymous,
            'status': d.status,
            'created_at': d.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for d in donations.items],
        'total': donations.total,
        'pages': donations.pages,
        'current_page': donations.page
    })

@app.route('/api/admin/donations/<int:donation_id>/status', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_update_donation_status(donation_id):
    """Обновить статус пожертвования"""
    data = request.json
    
    if not data.get('status'):
        return jsonify({
            'success': False,
            'message': 'Status is required'
        }), 400
    
    donation = Donation.query.get_or_404(donation_id)
    
    old_status = donation.status
    donation.status = data['status']
    
    try:
        db.session.commit()
        
        log_audit('update', 'donation', donation_id, 
                 f'Updated donation status from {old_status} to {donation.status}')
        
        return jsonify({
            'success': True,
            'message': 'Donation status updated'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating donation: {str(e)}'
        }), 500

# Получение логов аудита
@app.route('/api/admin/audit-logs', methods=['GET'])
@role_required('admin')
def get_audit_logs():
    """Получить логи аудита"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    admin_id = request.args.get('admin_id', type=int)
    
    query = AuditLog.query
    
    if admin_id:
        query = query.filter_by(admin_id=admin_id)
    
    logs = query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'logs': [{
            'id': log.id,
            'admin_id': log.admin_id,
            'admin_name': log.admin.full_name if log.admin else 'Unknown',
            'action': log.action,
            'entity_type': log.entity_type,
            'entity_id': log.entity_id,
            'details': log.details,
            'ip_address': log.ip_address,
            'created_at': log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        } for log in logs.items],
        'total': logs.total,
        'pages': logs.pages,
        'current_page': logs.page
    })

# Статистика для админки
@app.route('/api/admin/stats', methods=['GET'])
@login_required
def admin_get_stats():
    """Расширенная статистика для админки"""
    total_donations = Donation.query.count()
    total_amount = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    pending_donations = Donation.query.filter_by(status='ожидает').count()
    processed_donations = Donation.query.filter_by(status='обработано').count()
    
    total_fighters = Fighter.query.count()
    verified_fighters = Fighter.query.filter_by(is_verified=True).count()
    
    total_volunteers = Volunteer.query.count()
    active_volunteers = Volunteer.query.filter_by(is_active=True).count()
    
    # Статистика по дням
    today = datetime.utcnow().date()
    week_ago = today - timedelta(days=7)
    
    daily_stats = []
    for i in range(7):
        day = week_ago + timedelta(days=i)
        day_donations = Donation.query.filter(
            db.func.date(Donation.created_at) == day
        ).all()
        
        daily_stats.append({
            'date': day.strftime('%Y-%m-%d'),
            'count': len(day_donations),
            'amount': sum(d.amount for d in day_donations)
        })
    
    return jsonify({
        'success': True,
        'stats': {
            'donations': {
                'total': total_donations,
                'total_amount': total_amount,
                'pending': pending_donations,
                'processed': processed_donations
            },
            'fighters': {
                'total': total_fighters,
                'verified': verified_fighters
            },
            'volunteers': {
                'total': total_volunteers,
                'active': active_volunteers
            },
            'daily_stats': daily_stats
        }
    })
    
# ==================== 2FA ROUTES ====================

@app.route('/api/auth/2fa/setup', methods=['GET'])
@login_required
@require_2fa_setup
def setup_2fa():
    """Начать настройку 2FA"""
    try:
        user = request.current_user
        
        # Генерируем данные для настройки
        setup_data = TwoFactorAuth.setup_2fa(user)
        
        # Не возвращаем секрет напрямую в продакшене
        # В продакшене секрет должен передаваться только через QR код
        response_data = {
            'provisioning_uri': setup_data['provisioning_uri'],
            'qr_code': setup_data['qr_code'],
            'backup_codes': setup_data['backup_codes']
        }
        
        # Логируем начало настройки
        log_audit('2fa_setup_started', 'user', user.id, 'Started 2FA setup')
        
        return jsonify({
            'success': True,
            'message': 'Настройте 2FA в приложении аутентификатора',
            'data': response_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка настройки 2FA: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/enable', methods=['POST'])
@login_required
def enable_2fa():
    """Включить 2FA после настройки"""
    try:
        data = request.json
        user = request.current_user
        
        # Проверяем токен
        if not data or not data.get('token'):
            return jsonify({
                'success': False,
                'message': 'Токен обязателен'
            }), 400
        
        token = data['token']
        
        # Включаем 2FA
        success, message = TwoFactorAuth.enable_2fa(user, token)
        
        if success:
            # Очищаем неудачные попытки
            TwoFactorAuth.clear_failed_attempts(user.username)
            
            return jsonify({
                'success': True,
                'message': message,
                'two_factor_enabled': True
            })
        else:
            # Записываем неудачную попытку
            TwoFactorAuth.record_failed_attempt(
                user.username, 
                user.id, 
                reason='2fa_enable_failed'
            )
            
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка включения 2FA: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/disable', methods=['POST'])
@login_required
@require_2fa_enabled
def disable_2fa():
    """Отключить 2FA"""
    try:
        data = request.json
        user = request.current_user
        
        # Для отключения 2FA требуем либо пароль, либо токен
        password = data.get('password')
        token = data.get('token')
        
        if not password and not token:
            return jsonify({
                'success': False,
                'message': 'Требуется пароль или токен 2FA'
            }), 400
        
        # Отключаем 2FA
        success, message = TwoFactorAuth.disable_2fa(user, password, token)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'two_factor_enabled': False
            })
        else:
            # Записываем неудачную попытку
            TwoFactorAuth.record_failed_attempt(
                user.username, 
                user.id, 
                reason='2fa_disable_failed'
            )
            
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка отключения 2FA: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/verify', methods=['POST'])
def verify_2fa():
    """Проверка 2FA токена (используется после успешного ввода пароля)"""
    try:
        data = request.json
        
        if not data or not data.get('temp_token') or not data.get('token'):
            return jsonify({
                'success': False,
                'message': 'Требуется временный токен и код 2FA'
            }), 400
        
        temp_token = data['token']
        two_factor_token = data['two_factor_token']
        use_backup = data.get('use_backup', False)
        
        # Декодируем временный токен
        try:
            payload = jwt.decode(
                temp_token,
                app.config['JWT_SECRET_KEY'],
                algorithms=['HS256'],
                options={'verify_exp': False}  # Не проверяем срок, так как это временный токен
            )
            
            if payload.get('type') != 'temp_2fa':
                raise AuthError('Invalid token type')
            
            user_id = payload['sub']
            user = AdminUser.query.get(user_id)
            
            if not user or not user.is_active:
                raise AuthError('User not found or inactive')
            
        except jwt.InvalidTokenError:
            return jsonify({
                'success': False,
                'message': 'Неверный временный токен'
            }), 401
        
        # Проверяем 2FA токен
        if not TwoFactorAuth.verify_2fa_token(user, two_factor_token, use_backup):
            # Записываем неудачную попытку
            TwoFactorAuth.record_failed_attempt(
                user.username, 
                user.id, 
                reason='2fa_failed'
            )
            
            return jsonify({
                'success': False,
                'message': 'Неверный код 2FA'
            }), 401
        
        # 2FA успешно пройдена
        TwoFactorAuth.clear_failed_attempts(user.username)
        
        # Создаём полноценный access токен
        access_token = create_access_token(
            user.id, 
            user.username, 
            user.role, 
            two_factor_verified=True
        )
        refresh_token = create_refresh_token(user.id)
        
        # Обновляем время последнего входа
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Логируем успешный вход с 2FA
        log_audit('login_2fa', 'user', user.id, 'Logged in with 2FA')
        
        return jsonify({
            'success': True,
            'message': '2FA успешно пройдена',
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user': user.to_dict_without_secrets()
        })
        
    except AuthError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 401
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка проверки 2FA: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/backup/regenerate', methods=['POST'])
@login_required
@require_2fa_enabled
def regenerate_backup_codes():
    """Регенерировать резервные коды"""
    try:
        data = request.json
        user = request.current_user
        
        if not data or not data.get('token'):
            return jsonify({
                'success': False,
                'message': 'Токен 2FA обязателен'
            }), 400
        
        token = data['token']
        
        # Регенерируем коды
        success, message, backup_codes = TwoFactorAuth.regenerate_backup_codes(user, token)
        
        if success:
            # Предупреждение: старые коды больше не действительны
            log_audit('2fa_backup_regenerated', 'user', user.id, 'Regenerated backup codes')
            
            return jsonify({
                'success': True,
                'message': message,
                'backup_codes': backup_codes,
                'warning': 'Старые резервные коды больше не действительны!'
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Ошибка регенерации кодов: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/status', methods=['GET'])
@login_required
def get_2fa_status():
    """Получить статус 2FA"""
    user = request.current_user
    
    return jsonify({
        'success': True,
        'two_factor_enabled': user.two_factor_enabled,
        'two_factor_setup': bool(user.two_factor_secret),
        'last_used': user.two_factor_last_used.strftime('%Y-%m-%d %H:%M:%S') if user.two_factor_last_used else None
    })
    
# Добавляем маршрут для проверки необходимости 2FA
@app.route('/api/auth/check-2fa', methods=['POST'])
def check_2fa_requirement():
    """Проверить, требуется ли 2FA для пользователя"""
    data = request.json
    
    if not data or not data.get('username'):
        return jsonify({
            'success': False,
            'message': 'Username required'
        }), 400
    
    user = AdminUser.query.filter_by(username=data['username']).first()
    
    if not user:
        return jsonify({
            'success': False,
            'message': 'User not found'
        }), 404
    
    return jsonify({
        'success': True,
        'two_factor_enabled': user.two_factor_enabled,
        'two_factor_required': user.two_factor_enabled
    })

# Обработчик ошибок для JWT
@app.errorhandler(AuthError)
def handle_auth_error(e):
    return jsonify({
        'success': False,
        'message': str(e)
    }), 401
    
# Глобальный обработчик ошибок валидации
@app.errorhandler(ValidationError)
def handle_validation_error(err):
    return jsonify({
        'success': False,
        'message': 'Ошибка валидации данных',
        'errors': err.messages
    }), 400

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)