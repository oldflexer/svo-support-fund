"""
Public API endpoints
"""

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from datetime import datetime
import pyotp
import json

from models import db, UnitRequest, NewsArticle, Donation, Volunteer, AssistanceType
from schemas import validate_request, SCHEMAS
from utils.helpers import paginate_results, format_date, format_currency

public_bp = Blueprint('public', __name__)

@public_bp.route('/api/unit-requests/public', methods=['GET'])
@cross_origin()
def get_public_unit_requests():
    """Get current unit requests (public endpoint)"""
    try:
        # Get filtering parameters
        urgency = request.args.get('urgency')
        status = request.args.get('status', 'новая')
        
        # Build query
        query = UnitRequest.query.filter(
            UnitRequest.status.in_(['новая', 'в обработке'])
        )
        
        if urgency:
            query = query.filter(UnitRequest.urgency == urgency)
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Execute query
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format results
        results = []
        for request in paginated.items:
            # Calculate collection progress
            collected = 0
            needed = 1  # Avoid division by zero
            
            # Get donations for this request
            donations = Donation.query.filter(
                Donation.unit_request_id == request.id,
                Donation.status == 'обработано'
            ).all()
            
            for donation in donations:
                collected += donation.amount
            
            # Needed amount (approximately 10000 rubles per fighter)
            needed = request.quantity * 10000
            
            progress = {
                'collected': collected,
                'needed': needed,
                'percentage': min(100, int((collected / needed) * 100)) if needed > 0 else 0
            }
            
            results.append({
                'id': request.id,
                'unit_name': request.unit_name,
                'unit_commander': request.unit_commander,
                'contact_person': request.contact_person,
                'phone': request.phone,
                'email': request.email,
                'region': request.region,
                'needs': json.loads(request.needs),
                'urgency': request.urgency,
                'urgency_class': get_urgency_class(request.urgency),
                'quantity': request.quantity,
                'additional_info': request.additional_info,
                'status': request.status,
                'verification_status': request.verification_status,
                'created_at': format_date(request.created_at),
                'updated_at': format_date(request.updated_at),
                'progress': progress,
                'assigned_admin': request.assigned_admin.to_dict_without_secrets() if request.assigned_admin else None
            })
        
        return jsonify({
            'success': True,
            'data': {
                'requests': results,
                'pagination': {
                    'page': paginated.page,
                    'per_page': paginated.per_page,
                    'total_pages': paginated.pages,
                    'total_items': paginated.total
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting unit requests: {str(e)}'
        }), 500


@public_bp.route('/api/unit-requests', methods=['POST'])
@cross_origin()
def create_unit_request():
    """Create new unit request"""
    try:
        # Validate data
        data = validate_request('unit_request_create', request.json)
        
        # Create new request
        new_request = UnitRequest(
            unit_name=data['unit_name'],
            unit_commander=data['unit_commander'],
            contact_person=data['contact_person'],
            phone=data['phone'],
            email=data.get('email'),
            region=data['region'],
            needs=json.dumps(data['needs']),
            urgency=data.get('urgency', 'обычно'),
            quantity=data['quantity'],
            additional_info=data.get('additional_info'),
            status='новая',
            verification_status='не проверена'
        )
        
        db.session.add(new_request)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Request created successfully',
            'data': {
                'id': new_request.id,
                'created_at': new_request.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating unit request: {str(e)}'
        }), 400


@public_bp.route('/api/news', methods=['GET'])
@cross_origin()
def get_news():
    """Get news and front reports"""
    try:
        # Get parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        category = request.args.get('category')
        is_featured = request.args.get('is_featured', type=bool)
        
        # Build query
        query = NewsArticle.query.filter(NewsArticle.is_published == True)
        
        if category:
            query = query.filter(NewsArticle.category == category)
        
        if is_featured is not None:
            query = query.filter(NewsArticle.is_featured == is_featured)
        
        # Sort: featured first, then by publication date
        query = query.order_by(
            NewsArticle.is_featured.desc(),
            NewsArticle.published_at.desc(),
            NewsArticle.created_at.desc()
        )
        
        # Pagination
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        
        # Format results
        results = []
        for article in paginated.items:
            # Get main image
            main_image = None
            if article.images:
                main_image = next((img.image_url for img in article.images if img.is_main), None)
                if not main_image:
                    main_image = article.images[0].image_url
            
            # Calculate reading time (approximately 200 words per minute)
            word_count = len(article.content.split())
            read_time = max(1, int(word_count / 200))
            
            results.append({
                'id': article.id,
                'title': article.title,
                'slug': article.slug,
                'excerpt': article.excerpt,
                'content': article.content,
                'category': article.category,
                'author': article.author,
                'source': article.source,
                'region': article.region,
                'is_published': article.is_published,
                'is_verified': article.is_verified,
                'is_featured': article.is_featured,
                'views_count': article.views_count,
                'published_at': format_date(article.published_at),
                'created_at': format_date(article.created_at),
                'updated_at': format_date(article.updated_at),
                'tags': json.loads(article.tags) if article.tags else [],
                'main_image': main_image,
                'read_time': read_time
            })
        
        return jsonify({
            'success': True,
            'data': {
                'articles': results,
                'pagination': {
                    'page': paginated.page,
                    'per_page': paginated.per_page,
                    'total_pages': paginated.pages,
                    'total_items': paginated.total
                }
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting news: {str(e)}'
        }), 500


@public_bp.route('/api/news/<slug>', methods=['GET'])
@cross_origin()
def get_news_article(slug):
    """Get specific news article"""
    try:
        article = NewsArticle.query.filter_by(slug=slug, is_published=True).first()
        
        if not article:
            return jsonify({
                'success': False,
                'message': 'Article not found'
            }), 404
        
        # Get main image
        main_image = None
        images = []
        if article.images:
            main_image = next((img.image_url for img in article.images if img.is_main), None)
            if not main_image:
                main_image = article.images[0].image_url
            
            # Format images
            images = [{
                'id': img.id,
                'image_url': img.image_url,
                'caption': img.caption,
                'is_main': img.is_main,
                'order': img.order
            } for img in article.images]
        
        # Calculate reading time
        word_count = len(article.content.split())
        read_time = max(1, int(word_count / 200))
        
        # Increase view counter
        article.views_count += 1
        db.session.commit()
        
        result = {
            'id': article.id,
            'title': article.title,
            'slug': article.slug,
            'excerpt': article.excerpt,
            'content': article.content,
            'category': article.category,
            'author': article.author,
            'source': article.source,
            'region': article.region,
            'is_published': article.is_published,
            'is_verified': article.is_verified,
            'is_featured': article.is_featured,
            'views_count': article.views_count,
            'published_at': format_date(article.published_at),
            'created_at': format_date(article.created_at),
            'updated_at': format_date(article.updated_at),
            'tags': json.loads(article.tags) if article.tags else [],
            'main_image': main_image,
            'images': images,
            'read_time': read_time
        }
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting news article: {str(e)}'
        }), 500


@public_bp.route('/api/donate', methods=['POST'])
@cross_origin()
def create_donation():
    """Create donation"""
    try:
        # Validate data
        data = validate_request('donation_create', request.json)
        
        # Create donation
        new_donation = Donation(
            donor_name=data['name'],
            amount=data['amount'],
            fighter_id=data.get('fighter_id'),
            assistance_type_id=data.get('assistance_type_id'),
            message=data.get('message'),
            is_anonymous=data.get('is_anonymous', False),
            status='ожидает'
        )
        
        db.session.add(new_donation)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Donation created successfully',
            'data': {
                'id': new_donation.id,
                'created_at': new_donation.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error creating donation: {str(e)}'
        }), 400


@public_bp.route('/api/volunteer/register', methods=['POST'])
@cross_origin()
def register_volunteer():
    """Register volunteer"""
    try:
        # Validate data
        data = validate_request('volunteer_create', request.json)
        
        # Create volunteer
        new_volunteer = Volunteer(
            name=data['name'],
            email=data['email'],
            phone=data.get('phone'),
            skills=data.get('skills'),
            city=data['city'],
            can_deliver=data.get('can_deliver', False)
        )
        
        db.session.add(new_volunteer)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'You have successfully registered as a volunteer',
            'data': {
                'id': new_volunteer.id,
                'created_at': new_volunteer.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error registering volunteer: {str(e)}'
        }), 400


@public_bp.route('/api/stats', methods=['GET'])
@cross_origin()
def get_stats():
    """Get fund statistics"""
    try:
        # Calculate statistics
        total_donations = db.session.query(
            db.func.sum(Donation.amount)
        ).filter(
            Donation.status == 'обработано'
        ).scalar() or 0
        
        total_units_helped = db.session.query(
            db.func.count(UnitRequest.id)
        ).filter(
            UnitRequest.status.in_(['выполнена', 'в обработке'])
        ).scalar() or 0
        
        total_volunteers = Volunteer.query.filter(
            Volunteer.is_active == True
        ).count()
        
        return jsonify({
            'success': True,
            'data': {
                'total_donated': total_donations,
                'total_units': total_units_helped,
                'total_volunteers': total_volunteers
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting statistics: {str(e)}'
        }), 500


def get_urgency_class(urgency):
    """Get CSS class for urgency"""
    classes = {
        'критично': 'urgency-critical',
        'срочно': 'urgency-high',
        'обычно': 'urgency-normal'
    }
    return classes.get(urgency, 'urgency-normal')