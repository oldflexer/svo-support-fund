from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import jwt
from schemas import validate_request_data, SCHEMAS
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

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database with test data
def init_db():
    with app.app_context():
        db.create_all()
        
        # Create default admin if none exists
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
            
            # Create test moderator
            moderator = AdminUser(
                username='moderator',
                email='moderator@zaschitnikam.ru',
                full_name='Модератор',
                role='moderator',
                is_active=True
            )
            moderator.set_password('Moderator123!')
            db.session.add(moderator)
        
        # Add assistance types if none exist
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
# ==================== UNIT REQUESTS ====================

@app.route('/api/unit-requests', methods=['POST'])
def create_unit_request():
    """Create a unit request"""
    data = request.json
    
    try:
        # Validate required fields
        required_fields = ['unit_name', 'unit_commander', 'contact_person', 'phone', 'region', 'needs', 'quantity']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Field {field} is required'
                }), 400
        
        # Create the request
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
        
        # Log the request creation
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
    """Get public unit requests"""
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
    
    # Show only verified and active requests
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
        'progress': calculate_request_progress(r.id)  # Function to calculate collection progress
    } for r in requests])

def calculate_request_progress(request_id):
    """Calculate collection progress for a request"""
    total_needed = 0
    total_collected = 0
    
    # Here you can add logic to calculate the cost of needs
    # For now, return random values for demonstration
    import random
    return {
        'collected': random.randint(10000, 50000),
        'needed': random.randint(100000, 300000),
        'percentage': random.randint(10, 50)
    }
# ==================== ADMIN ROUTES FOR REQUESTS ====================

@app.route('/api/admin/unit-requests', methods=['GET'])
@login_required
def admin_get_unit_requests():
    """Get all unit requests (for admin panel)"""
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
    """Update request status"""
    data = request.json
    
    unit_request = UnitRequest.query.get_or_404(request_id)
    
    try:
        if 'status' in data:
            old_status = unit_request.status
            unit_request.status = data['status']
            
            # If request is assigned to an admin
            if data['status'] == 'в обработке' and not unit_request.assigned_admin_id:
                unit_request.assigned_admin_id = request.current_user.id
            
            # Log status change
            log_audit('unit_request_status_updated', 'unit_request', request_id,
                     f'Status changed from "{old_status}" to "{data["status"]}"')
        
        if 'verification_status' in data:
            old_verification = unit_request.verification_status
            unit_request.verification_status = data['verification_status']
            
            log_audit('unit_request_verification_updated', 'unit_request', request_id,
                     f'Verification status changed from "{old_verification}" to "{data["verification_status"]}"')
        
        unit_request.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Request status updated'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating status: {str(e)}'
        }), 500
@app.route('/api/admin/unit-requests/<int:request_id>/assign', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_assign_unit_request(request_id):
    """Assign a request to an administrator"""
    data = request.json
    
    if not data.get('admin_id'):
        return jsonify({
            'success': False,
            'message': 'Administrator ID is required'
        }), 400
    
    unit_request = UnitRequest.query.get_or_404(request_id)
    admin = AdminUser.query.get(data['admin_id'])
    
    if not admin:
        return jsonify({
            'success': False,
            'message': 'Administrator not found'
        }), 404
    
    try:
        old_admin = unit_request.assigned_admin_id
        unit_request.assigned_admin_id = admin.id
        unit_request.status = 'in progress'
        unit_request.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        log_audit('unit_request_assigned', 'unit_request', request_id,
                 f'Request assigned from administrator {old_admin} to {admin.id}')
        
        return jsonify({
            'success': True,
            'message': f'Request assigned to {admin.full_name}'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error assigning request: {str(e)}'
        }), 500

@app.route('/api/assistance/types', methods=['GET'])
def get_assistance_types():
    """Get assistance types"""
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
            'медицина': 'Medical Assistance',
            'техника': 'Technical Equipment',
            'снаряжение': 'Equipment',
            'прочее': 'Other Assistance'
        }.get(t.category, t.category)
    } for t in types])

# ==================== NEWS AND FRONTLINE REPORTS ====================

@app.route('/api/news', methods=['GET'])
def get_news():
    """Get news and frontline reports"""
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
    
    # Sort by publication date if available, otherwise by creation date
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
            'read_time': calculate_read_time(article.content)  # Reading time in minutes
        } for article in articles.items],
        'total': articles.total,
        'pages': articles.pages,
        'current_page': articles.page
    })
def calculate_read_time(content):
    """Calculate reading time for an article"""
    words_per_minute = 200
    word_count = len(content.split())
    read_time = max(1, round(word_count / words_per_minute))
    return read_time

@app.route('/api/news/<string:slug>', methods=['GET'])
def get_news_article(slug):
    """Get a specific news article"""
    article = NewsArticle.query.filter_by(slug=slug, is_published=True).first_or_404()
    
    # Increase view counter
    article.views_count += 1
    db.session.commit()
    
    # Get related articles
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
    """Get list of news categories"""
    categories = db.session.query(
        NewsArticle.category,
        db.func.count(NewsArticle.id).label('count')
    ).filter_by(is_published=True).group_by(NewsArticle.category).all()
    
    return jsonify([{
        'name': cat[0],
        'count': cat[1],
        'display_name': {
            'новости': 'News',
            'сводка': 'Frontline Reports',
            'отчёт': 'Help Reports',
            'история': 'Soldiers' Stories'
        }.get(cat[0], cat[0])
    } for cat in categories])

@app.route('/api/news/regions', methods=['GET'])
def get_news_regions():
    """Get list of regions for news"""
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
# ==================== ADMIN ROUTES FOR NEWS ====================

@app.route('/api/admin/news', methods=['POST'])
@role_required('admin', 'moderator')
def admin_create_news():
    """Create news article"""
    data = request.json
    
    try:
        # Generate slug from title
        import re
        from transliterate import translit
        
        title = data['title']
        slug_base = translit(title, 'ru', reversed=True).lower()
        slug_base = re.sub(r'[^a-z0-9]+', '-', slug_base).strip('-')
        
        # Check slug uniqueness
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
        
        log_audit('news_created', 'news', article.id, f'News article "{title}" created')
        
        return jsonify({
            'success': True,
            'message': 'News article created',
            'article': {
                'id': article.id,
                'slug': article.slug
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error creating news article: {str(e)}'
        }), 500

@app.route('/api/admin/news/<int:article_id>', methods=['PUT'])
@role_required('admin', 'moderator')
def admin_update_news(article_id):
    """Update news article"""
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
        
        log_audit('news_updated', 'news', article_id, f'News article "{article.title}" updated')
        
        return jsonify({
            'success': True,
            'message': 'News article updated'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Error updating news article: {str(e)}'
        }), 500
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """Get fund statistics"""

    # Total donations amount
    total_donated = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    
    # Recent donations
    recent_donations = Donation.query.order_by(Donation.created_at.desc()).limit(5).all()
    
    # Volunteers
    total_volunteers = Volunteer.query.filter_by(is_active=True).count()
    
    # Active equipment requests
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
    """Create a donation"""
    try:
        validated_data = validate_request_data('donation_create', request.json)
        
        # Check amount
        if validated_data['amount'] < 100:
            return jsonify({
                'success': False,
                'message': 'Minimum donation amount is 100 rubles'
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
            'message': 'Thank you for your support of the participants of the SVO!',
            'donation_id': donation.id,
            'receipt_number': f"DON-{donation.id:06d}"
        })
        
    except ValidationError as err:
        return jsonify({
            'success': False,
            'message': 'Error validating donation data',
            'errors': err.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/volunteer/register', methods=['POST'])
def register_volunteer():
    """Register as a volunteer"""
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
            'message': 'Thank you for your willingness to help! We will contact you shortly.',
            'volunteer_id': volunteer.id
        })
    
    except ValidationError as err:
        return jsonify({
            'success': False,
            'message': 'Error validating volunteer data',
            'errors': err.messages
        }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
# ==================== EQUIPMENT REQUESTS ====================

@app.route('/api/equipment/request', methods=['POST'])
def create_equipment_request():
    """Create an equipment request"""
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
            'message': 'Equipment request created',
            'request_id': request_item.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@app.route('/api/needs/urgent', methods=['GET'])
def get_urgent_needs():
    """Get urgent needs"""

    return jsonify()  # Limit to 10 urgent needs
@app.route('/api/deliveries/planned', methods=['GET'])
def get_planned_deliveries():
    """Get planned deliveries"""
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
    """Administrator authentication"""
    #data = request.json
    try:
        # Validate data
        #validated_data = validate_request_data('login', request.json)
        data = request.validated_data

        # Check rate limit
        allowed, wait_time = TwoFactorAuth.check_rate_limit(
            data['username'], 
            request.remote_addr
        )
        
        if not allowed:
            return jsonify({
                'success': False,
                'message': f'Too many attempts. Try again in {wait_time} seconds.',
                'wait_time': wait_time
            }), 429

        # Use validated data
        # Find user
        user = AdminUser.query.filter_by(username=data['username']).first()
        if not user:
            TwoFactorAuth.record_failed_attempt(data['username'], reason='user_not_found')
            return jsonify({
                'success': False,
                'message': 'Invalid credentials'
            }), 401
        
        # Check password
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
        
        # Check account status
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
        
        # If 2FA is enabled, return temporary token
        if user.two_factor_enabled:
            # Create temporary token for 2FA
            temp_token = jwt.encode({
                'exp': datetime.now(datetime.timezone.utc) + timedelta(minutes=5),
                'iat': datetime.now(datetime.timezone.utc),
                'sub': user.id,
                'type': 'temp_2fa',
                'username': user.username
            }, app.config['JWT_SECRET_KEY'], algorithm='HS256')
            
            # Log successful password entry
            log_audit('login_password_ok', 'user', user.id, 'Password correct, 2FA required')
            
            return jsonify({
                'success': True,
                'message': 'Two-factor authentication is required',
                'two_factor_required': True,
                'temp_token': temp_token,
                'user_id': user.id,
                'username': user.username
            })
        
        # If 2FA is not enabled, create regular tokens
        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Create tokens
        access_token = create_access_token(user.id, user.username, user.role)
        refresh_token = create_refresh_token(user.id)
        
        # Clear failed attempts
        TwoFactorAuth.clear_failed_attempts(user.username)
        # Log successful login
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
            'message': 'Validation error',
            'errors': err.messages
        }), 400
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Login error: {str(e)}'
        }), 500

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token"""
    try:
        data = request.json
        if not data or not data.get('refresh_token'):
            return jsonify({
                'success': False,
                'message': 'Refresh token required'
            }), 400
        
        # Verify refresh token
        payload = verify_token(data['refresh_token'])
        
        if payload.get('type') != 'refresh':
            return jsonify({
                'success': False,
                'message': 'Invalid token type'
            }), 400
        
        # Get user
        user = AdminUser.query.get(payload['sub'])
        if not user or not user.is_active:
            return jsonify({
                'success': False,
                'message': 'User not found or inactive'
            }), 401
        
        # Create new access token
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
    """Logout"""
    log_audit('logout')
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })

@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current user information"""
    return jsonify({
        'success': True,
        'user': request.current_user.to_dict()
    })
# ==================== ADMIN ROUTES ====================

# User Management
@app.route('/api/admin/users', methods=['GET'])
@role_required('admin')
def get_admin_users():
    """Get list of administrators"""
    users = AdminUser.query.order_by(AdminUser.created_at.desc()).all()
    return jsonify({
        'success': True,
        'users': [user.to_dict() for user in users]
    })

@app.route('/api/admin/users', methods=['POST'])
@role_required('admin')
@validate_request('admin_create')
def create_admin_user():
    """Create new administrator"""
    # Data is already validated and available in request.validated_data
    data = request.validated_data
    
    # Check uniqueness
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
    """Update administrator"""
    data = request.json
    
    user = AdminUser.query.get_or_404(user_id)
    
    # Cannot edit yourself
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
# Donation Management
@app.route('/api/admin/donations', methods=['GET'])
@login_required
def admin_get_donations():
    """Get all donations"""
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
    """Update donation status"""
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

# Get audit logs
@app.route('/api/admin/audit-logs', methods=['GET'])
@role_required('admin')
def get_audit_logs():
    """Get audit logs"""
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
# ==================== ADMIN STATISTICS ====================

@app.route('/api/admin/stats', methods=['GET'])
@login_required
def admin_get_stats():
    """Extended statistics for admin panel"""
    total_donations = Donation.query.count()
    total_amount = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    pending_donations = Donation.query.filter_by(status='ожидает').count()
    processed_donations = Donation.query.filter_by(status='обработано').count()
    
    total_volunteers = Volunteer.query.count()
    active_volunteers = Volunteer.query.filter_by(is_active=True).count()
    
    # Statistics by days
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
    """Start 2FA setup"""
    try:
        user = request.current_user
        
        # Generate setup data
        setup_data = TwoFactorAuth.setup_2fa(user)
        
        # Do not return secret directly in production
        # In production, secret should be passed only through QR code
        response_data = {
            'provisioning_uri': setup_data['provisioning_uri'],
            'qr_code': setup_data['qr_code'],
            'backup_codes': setup_data['backup_codes']
        }
        
        # Log setup start
        log_audit('2fa_setup_started', 'user', user.id, 'Started 2FA setup')
        
        return jsonify({
            'success': True,
            'message': 'Configure 2FA in your authenticator app',
            'data': response_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error setting up 2FA: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/enable', methods=['POST'])
@login_required
def enable_2fa():
    """Enable 2FA after setup"""
    try:
        data = request.json
        user = request.current_user
        
        # Check token
        if not data or not data.get('token'):
            return jsonify({
                'success': False,
                'message': 'Token is required'
            }), 400
        
        token = data['token']
        
        # Enable 2FA
        success, message = TwoFactorAuth.enable_2fa(user, token)
        
        if success:
            # Clear failed attempts
            TwoFactorAuth.clear_failed_attempts(user.username)
            
            return jsonify({
                'success': True,
                'message': message,
                'two_factor_enabled': True
            })
        else:
            # Record failed attempt
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
            'message': f'Error enabling 2FA: {str(e)}'
        }), 500
@app.route('/api/auth/2fa/disable', methods=['POST'])
@login_required
@require_2fa_enabled
def disable_2fa():
    """Disable 2FA"""
    try:
        data = request.json
        user = request.current_user
        
        # Require either password or 2FA token to disable 2FA
        password = data.get('password')
        token = data.get('token')
        
        if not password and not token:
            return jsonify({
                'success': False,
                'message': 'Password or 2FA token is required'
            }), 400
        
        # Disable 2FA
        success, message = TwoFactorAuth.disable_2fa(user, password, token)
        
        if success:
            return jsonify({
                'success': True,
                'message': message,
                'two_factor_enabled': False
            })
        else:
            # Record failed attempt
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
            'message': f'Error disabling 2FA: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/verify', methods=['POST'])
def verify_2fa():
    """Verify 2FA token (used after successful password entry)"""
    try:
        data = request.json

        if not data or not data.get('temp_token') or not data.get('token'):
            return jsonify({
                'success': False,
                'message': 'Temporary token and 2FA code are required'
            }), 400

        # temp_token = data['token']
        # two_factor_token = data['two_factor_token']
        temp_token = data['temp_token']
        two_factor_token = data['temp_token']
        use_backup = data.get('use_backup', False)

        # Decode temporary token
        try:
            payload = jwt.decode(
                temp_token,
                app.config['JWT_SECRET_KEY'],
                algorithms=['HS256'],
                options={'verify_exp': False}  # Don't verify expiry for temporary token
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
                'message': 'Invalid temporary token'
            }), 401

        # Verify 2FA token
        if not TwoFactorAuth.verify_2fa_token(user, two_factor_token, use_backup):
            # Record failed attempt
            TwoFactorAuth.record_failed_attempt(
                user.username,
                user.id,
                reason='2fa_failed'
            )

            return jsonify({
                'success': False,
                'message': 'Invalid 2FA code'
            }), 401

        # 2FA successfully passed
        TwoFactorAuth.clear_failed_attempts(user.username)

        # Create full access token
        access_token = create_access_token(
            user.id,
            user.username,
            user.role,
            two_factor_verified=True
        )
        refresh_token = create_refresh_token(user.id)

        # Update last login time
        user.last_login = datetime.utcnow()
        db.session.commit()

        # Log successful login with 2FA
        log_audit('login_2fa', 'user', user.id, 'Logged in with 2FA')

        return jsonify({
            'success': True,
            'message': '2FA successfully passed',
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
            'message': f'Error verifying 2FA: {str(e)}'
        }), 500

# ==================== 2FA ROUTES ====================

@app.route('/api/auth/2fa/backup/regenerate', methods=['POST'])
@login_required
@require_2fa_enabled
def regenerate_backup_codes():
    """Regenerate backup codes"""
    try:
        data = request.json
        user = request.current_user
        
        if not data or not data.get('token'):
            return jsonify({
                'success': False,
                'message': '2FA token is required'
            }), 400
        
        token = data['token']
        
        # Regenerate codes
        success, message, backup_codes = TwoFactorAuth.regenerate_backup_codes(user, token)
        
        if success:
            # Warning: old codes are no longer valid
            log_audit('2fa_backup_regenerated', 'user', user.id, 'Regenerated backup codes')
            
            return jsonify({
                'success': True,
                'message': message,
                'backup_codes': backup_codes,
                'warning': 'Old backup codes are no longer valid!'
            })
        else:
            return jsonify({
                'success': False,
                'message': message
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error regenerating codes: {str(e)}'
        }), 500

@app.route('/api/auth/2fa/status', methods=['GET'])
@login_required
def get_2fa_status():
    """Get 2FA status"""
    user = request.current_user
    
    return jsonify({
        'success': True,
        'two_factor_enabled': user.two_factor_enabled,
        'two_factor_setup': bool(user.two_factor_secret),
        'last_used': user.two_factor_last_used.strftime('%Y-%m-%d %H:%M:%S') if user.two_factor_last_used else None
    })
    
# Add route to check 2FA requirement
@app.route('/api/auth/check-2fa', methods=['POST'])
def check_2fa_requirement():
    """Check if 2FA is required for user"""
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

# Error handler for JWT
@app.errorhandler(AuthError)
def handle_auth_error(e):
    return jsonify({
        'success': False,
        'message': str(e)
    }), 401
    
# Global error handler for validation
@app.errorhandler(ValidationError)
def handle_validation_error(err):
    return jsonify({
        'success': False,
        'message': 'Validation error',
        'errors': err.messages
    }), 400

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
