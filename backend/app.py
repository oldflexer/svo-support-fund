from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
from schemas import validate_request, validate_request_data, SCHEMAS
from marshmallow import ValidationError
from middleware import validate_json, validate_query_params
from models import NewsArticle, UnitRequest, db, bcrypt, AdminUser, AssistanceType, Donation, Volunteer, Delivery, AuditLog, EquipmentRequest
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
            "/api/assistance/types - типы помощи",
            "/api/unit-requests - потребности",
            "/api/stats - статистика",
            "/api/donate - сделать пожертвование",
            "/api/volunteer - стать волонтером"
        ]
    })

# ==================== ЗАЯВКИ ОТ ПОДРАЗДЕЛЕНИЙ ====================

@app.route('/api/unit-requests', methods=['POST'])
def create_unit_request():
    """Создать заявку от подразделения"""
    data = request.json
    
    try:
        # Валидация обязательных полей
        required_fields = ['unit_name', 'unit_commander', 'contact_person', 'phone', 'region', 'needs', 'quantity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Поле {field} обязательно для заполнения'
                }), 400
        
        # Создаём заявку
        unit_request = UnitRequest(
            unit_name=data['unit_name'],
            unit_commander=data['unit_commander'],
            contact_person=data['contact_person'],
            phone=data['phone'],
            email=data.get('email', ''),
            region=data['region'],
            needs=json.dumps(data['needs']),
            urgency=data.get('urgency', 'обычно'),
            quantity=data['quantity'],
            additional_info=data.get('additional_info', ''),
            status='новая',
            verification_status='не проверена'
        )
        
        db.session.add(unit_request)
        db.session.commit()
        
        # Логируем создание заявки
        log_audit('unit_request_created', 'unit_request', unit_request.id, 
                 f'Создана заявка от подразделения {unit_request.unit_name}')
        
        return jsonify({
            'success': True,
            'message': 'Заявка успешно отправлена! Мы свяжемся с вами для подтверждения.',
            'request_id': unit_request.id,
            'tracking_code': f"UNIT-REQ-{unit_request.id:06d}"
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка при создании заявки: {str(e)}'
        }), 500

@app.route('/api/unit-requests/public', methods=['GET'])
def get_public_unit_requests():
    """Получить заявки от подразделений для публичного просмотра"""
    status = request.args.get('status', 'новая')
    region = request.args.get('region')
    verified = request.args.get('verified', 'false').lower() == 'true'
    
    query = UnitRequest.query
    
    if status:
        query = query.filter_by(status=status)
    if region:
        query = query.filter_by(region=region)
    if verified:
        query = query.filter_by(verification_status='подтверждена')
    
    # Показываем только проверенные и активные заявки
    requests = query.filter(
        UnitRequest.verification_status == 'подтверждена',
        UnitRequest.status.in_(['новая', 'в обработке'])
    ).order_by(
        db.case(
            (UnitRequest.urgency == 'критично', 1),
            (UnitRequest.urgency == 'срочно', 2),
            else_=3
        ),
        UnitRequest.created_at.desc()
    ).limit(50).all()
    
    return jsonify([{
        'id': r.id,
        'unit_name': r.unit_name,
        'region': r.region,
        'needs': json.loads(r.needs) if r.needs else [],
        'urgency': r.urgency,
        'quantity': r.quantity,
        'status': r.status,
        'verification_status': r.verification_status,
        'created_at': r.created_at.strftime('%d.%m.%Y'),
        'urgency_class': {
            'критично': 'urgency-critical',
            'срочно': 'urgency-high',
            'обычно': 'urgency-normal'
        }.get(r.urgency, 'urgency-normal'),
        'progress': calculate_request_progress(r.id)  # Функция для расчёта прогресса сбора
    } for r in requests])

def calculate_request_progress(request_id):
    """Рассчитать прогресс сбора средств для заявки"""
    total_needed = 0
    total_collected = 0
    
    # Здесь можно добавить логику расчёта стоимости потребностей
    # Пока возвращаем случайные значения для демонстрации
    import random
    return {
        'collected': random.randint(10000, 50000),
        'needed': random.randint(100000, 300000),
        'percentage': random.randint(10, 50)
    }

# ==================== АДМИН МАРШРУТЫ ДЛЯ ЗАЯВОК ====================

@app.route('/api/admin/unit-requests', methods=['GET'])
@login_required
def admin_get_unit_requests():
    """Получить все заявки от подразделений (для админки)"""
    status = request.args.get('status')
    verification_status = request.args.get('verification_status')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = UnitRequest.query
    
    if status:
        query = query.filter_by(status=status)
    if verification_status:
        query = query.filter_by(verification_status=verification_status)
    
    requests = query.order_by(UnitRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'success': True,
        'requests': [{
            'id': r.id,
            'unit_name': r.unit_name,
            'unit_commander': r.unit_commander,
            'contact_person': r.contact_person,
            'phone': r.phone,
            'email': r.email,
            'region': r.region,
            'needs': json.loads(r.needs) if r.needs else [],
            'urgency': r.urgency,
            'quantity': r.quantity,
            'additional_info': r.additional_info,
            'status': r.status,
            'verification_status': r.verification_status,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': r.updated_at.strftime('%Y-%m-%d %H:%M:%S') if r.updated_at else None,
            'assigned_admin': r.assigned_admin.full_name if r.assigned_admin else None
        } for r in requests.items],
        'total': requests.total,
        'pages': requests.pages,
        'current_page': requests.page
    })

@app.route('/api/admin/unit-requests/<int:request_id>/status', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_update_unit_request_status(request_id):
    """Обновить статус заявки"""
    data = request.json
    
    unit_request = UnitRequest.query.get_or_404(request_id)
    
    try:
        if 'status' in data:
            old_status = unit_request.status
            unit_request.status = data['status']
            
            # Если заявка назначается на админа
            if data['status'] == 'в обработке' and not unit_request.assigned_admin_id:
                unit_request.assigned_admin_id = request.current_user.id
            
            # Логируем изменение статуса
            log_audit('unit_request_status_updated', 'unit_request', request_id,
                     f'Статус изменён с "{old_status}" на "{data["status"]}"')
        
        if 'verification_status' in data:
            old_verification = unit_request.verification_status
            unit_request.verification_status = data['verification_status']
            
            log_audit('unit_request_verification_updated', 'unit_request', request_id,
                     f'Статус проверки изменён с "{old_verification}" на "{data["verification_status"]}"')
        
        unit_request.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Статус заявки обновлён'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка обновления статуса: {str(e)}'
        }), 500

@app.route('/api/admin/unit-requests/<int:request_id>/assign', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_assign_unit_request(request_id):
    """Назначить заявку на администратора"""
    data = request.json
    
    if not data.get('admin_id'):
        return jsonify({
            'success': False,
            'message': 'ID администратора обязателен'
        }), 400
    
    unit_request = UnitRequest.query.get_or_404(request_id)
    admin = AdminUser.query.get(data['admin_id'])
    
    if not admin:
        return jsonify({
            'success': False,
            'message': 'Администратор не найден'
        }), 404
    
    try:
        old_admin = unit_request.assigned_admin_id
        unit_request.assigned_admin_id = admin.id
        unit_request.status = 'в обработке'
        unit_request.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        log_audit('unit_request_assigned', 'unit_request', request_id,
                 f'Заявка назначена с администратора {old_admin} на {admin.id}')
        
        return jsonify({
            'success': True,
            'message': f'Заявка назначена на {admin.full_name}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка назначения заявки: {str(e)}'
        }), 500

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

# ==================== НОВОСТИ И ФРОНТОВЫЕ СВОДКИ ====================

@app.route('/api/news', methods=['GET'])
def get_news():
    """Получить новости и фронтовые сводки"""
    category = request.args.get('category')
    region = request.args.get('region')
    featured = request.args.get('featured')
    limit = request.args.get('limit', 10, type=int)
    page = request.args.get('page', 1, type=int)
    
    query = NewsArticle.query.filter_by(is_published=True)
    
    if category:    
        query = query.filter_by(category=category)
    if region:
        query = query.filter_by(region=region)
    if featured and featured.lower() == 'true':
        query = query.filter_by(is_featured=True)
    
    # Сортируем по дате публикации, если есть, иначе по дате создания
    articles = query.order_by(
        db.case(
            (NewsArticle.published_at.isnot(None), NewsArticle.published_at),
            else_=NewsArticle.created_at
        ).desc()
    ).paginate(page=page, per_page=limit, error_out=False)
    
    return jsonify({
        'articles': [{
            'id': article.id,
            'title': article.title,
            'slug': article.slug,
            'excerpt': article.excerpt or article.content[:150] + '...',
            'category': article.category,
            'author': article.author,
            'source': article.source,
            'region': article.region,
            'is_featured': article.is_featured,
            'is_verified': article.is_verified,
            'views_count': article.views_count,
            'published_at': article.published_at.strftime('%d.%m.%Y %H:%M') if article.published_at else None,
            'created_at': article.created_at.strftime('%d.%m.%Y'),
            'tags': json.loads(article.tags) if article.tags else [],
            'main_image': next((img.image_url for img in article.images if img.is_main), None),
            'read_time': calculate_read_time(article.content)  # Время чтения в минутах
        } for article in articles.items],
        'total': articles.total,
        'pages': articles.pages,
        'current_page': articles.page
    })

def calculate_read_time(content):
    """Рассчитать время чтения статьи"""
    words_per_minute = 200
    word_count = len(content.split())
    read_time = max(1, round(word_count / words_per_minute))
    return read_time

@app.route('/api/news/<string:slug>', methods=['GET'])
def get_news_article(slug):
    """Получить конкретную новость"""
    article = NewsArticle.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Увеличиваем счётчик просмотров
    article.views_count += 1
    db.session.commit()
    
    # Получаем связанные статьи
    related_articles = NewsArticle.query.filter(
        NewsArticle.id != article.id,
        NewsArticle.is_published == True,
        db.or_(
            NewsArticle.category == article.category,
            NewsArticle.region == article.region
        )
    ).order_by(db.func.random()).limit(3).all()
    
    return jsonify({
        'article': {
            'id': article.id,
            'title': article.title,
            'slug': article.slug,
            'content': article.content,
            'category': article.category,
            'author': article.author,
            'source': article.source,
            'region': article.region,
            'is_featured': article.is_featured,
            'is_verified': article.is_verified,
            'views_count': article.views_count,
            'published_at': article.published_at.strftime('%d.%m.%Y %H:%M') if article.published_at else None,
            'created_at': article.created_at.strftime('%d.%m.%Y'),
            'tags': json.loads(article.tags) if article.tags else [],
            'images': [{
                'url': img.image_url,
                'caption': img.caption,
                'is_main': img.is_main
            } for img in article.images]
        },
        'related_articles': [{
            'id': ra.id,
            'title': ra.title,
            'slug': ra.slug,
            'excerpt': ra.excerpt or ra.content[:100] + '...',
            'category': ra.category,
            'published_at': ra.published_at.strftime('%d.%m.%Y') if ra.published_at else None
        } for ra in related_articles]
    })

@app.route('/api/news/categories', methods=['GET'])
def get_news_categories():
    """Получить список категорий новостей"""
    categories = db.session.query(
        NewsArticle.category,
        db.func.count(NewsArticle.id).label('count')
    ).filter_by(is_published=True).group_by(NewsArticle.category).all()
    
    return jsonify([{
        'name': cat[0],
        'count': cat[1],
        'display_name': {
            'новости': 'Новости фонда',
            'сводка': 'Фронтовые сводки',
            'отчёт': 'Отчёты о помощи',
            'история': 'Истории бойцов'
        }.get(cat[0], cat[0])
    } for cat in categories])

@app.route('/api/news/regions', methods=['GET'])
def get_news_regions():
    """Получить список регионов для новостей"""
    regions = db.session.query(
        NewsArticle.region,
        db.func.count(NewsArticle.id).label('count')
    ).filter(
        NewsArticle.is_published == True,
        NewsArticle.region.isnot(None)
    ).group_by(NewsArticle.region).all()
    
    return jsonify([{
        'name': region[0],
        'count': region[1]
    } for region in regions])

# ==================== АДМИН МАРШРУТЫ ДЛЯ НОВОСТЕЙ ====================

@app.route('/api/admin/news', methods=['POST'])
@role_required('admin', 'moderator')
def admin_create_news():
    """Создать новость"""
    data = request.json
    
    try:
        # Генерируем slug из заголовка
        import re
        from transliterate import translit
        
        title = data['title']
        slug_base = translit(title, 'ru', reversed=True).lower()
        slug_base = re.sub(r'[^a-z0-9]+', '-', slug_base).strip('-')
        
        # Проверяем уникальность slug
        counter = 1
        slug = slug_base
        while NewsArticle.query.filter_by(slug=slug).first():
            slug = f"{slug_base}-{counter}"
            counter += 1
        
        article = NewsArticle(
            title=title,
            slug=slug,
            excerpt=data.get('excerpt', ''),
            content=data['content'],
            category=data.get('category', 'новости'),
            author=data.get('author', ''),
            source=data.get('source', ''),
            region=data.get('region'),
            tags=json.dumps(data.get('tags', [])),
            is_published=data.get('is_published', False),
            is_verified=data.get('is_verified', False),
            is_featured=data.get('is_featured', False),
            published_at=datetime.utcnow() if data.get('is_published') else None,
            created_by_id=request.current_user.id
        )
        
        db.session.add(article)
        db.session.commit()
        
        log_audit('news_created', 'news', article.id, f'Создана новость "{title}"')
        
        return jsonify({
            'success': True,
            'message': 'Новость создана',
            'article': {
                'id': article.id,
                'slug': article.slug
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка создания новости: {str(e)}'
        }), 500

@app.route('/api/admin/news/<int:article_id>', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_update_news(article_id):
    """Обновить новость"""
    data = request.json
    article = NewsArticle.query.get_or_404(article_id)
    
    try:
        if 'title' in data and data['title'] != article.title:
            article.title = data['title']
        
        if 'content' in data:
            article.content = data['content']
        
        if 'excerpt' in data:
            article.excerpt = data['excerpt']
        
        if 'category' in data:
            article.category = data['category']
        
        if 'author' in data:
            article.author = data['author']
        
        if 'source' in data:
            article.source = data['source']
        
        if 'region' in data:
            article.region = data['region']
        
        if 'tags' in data:
            article.tags = json.dumps(data['tags'])
        
        if 'is_published' in data:
            article.is_published = data['is_published']
            if data['is_published'] and not article.published_at:
                article.published_at = datetime.utcnow()
        
        if 'is_verified' in data:
            article.is_verified = data['is_verified']
        
        if 'is_featured' in data:
            article.is_featured = data['is_featured']
        
        article.updated_at = datetime.utcnow()
        db.session.commit()
        
        log_audit('news_updated', 'news', article_id, f'Обновлена новость "{article.title}"')
        
        return jsonify({
            'success': True,
            'message': 'Новость обновлена'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Ошибка обновления новости: {str(e)}'
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Получить статистику фонда"""
    
    # Сумма пожертвований
    total_donated = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    
    # Последние пожертвования
    recent_donations = Donation.query.order_by(Donation.created_at.desc()).limit(5).all()
    
    # Волонтеры
    total_volunteers = Volunteer.query.filter_by(is_active=True).count()
    
    # Активные запросы на снаряжение
    active_requests = EquipmentRequest.query.filter_by(status='требуется').count()
    
    return jsonify({
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
    
    return jsonify()  # Ограничиваем 10 срочными потребностями

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
                'exp': datetime.now(datetime.timezone.utc) + timedelta(minutes=5),
                'iat': datetime.now(datetime.timezone.utc),
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
        
        # temp_token = data['token']
        # two_factor_token = data['two_factor_token']
        temp_token = data['temp_token']
        two_factor_token = data['temp_token']
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
