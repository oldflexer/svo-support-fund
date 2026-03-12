from tkinter import N

from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, NewsArticle
from forms import NewsForm
from utils import role_required, log_action
from . import admin_bp

# -------------------------------
# API: News
# -------------------------------

@admin_bp.route('/news', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_news():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    category = request.args.get('category', None)
    is_verified = request.args.get('verified', None)

    query = NewsArticle.query

    if category is not None:
        query = query.filter_by(category=category)

    if is_verified is not None:
        is_verified = is_verified.lower() == 'true'
        query = query.filter_by(is_verified=is_verified)

    pagination = query.order_by(NewsArticle.published_at.desc()).paginate(page=page, per_page=per_page)
    
    result = [{
        'id': a.id,
        'title': a.title,
        'slug': a.slug,
        'excerpt': a.excerpt,
        'category': a.category,
        'main_image': a.main_image,
        'is_verified': a.is_verified,
        'views_count': a.views_count,
        'read_time': a.read_time,
        'published_at': a.published_at.isoformat() + 'Z' if a.published_at else None
    } for a in pagination]
    
    return jsonify(result), 200

@admin_bp.route('/news/<slug>', methods=['GET'])
@jwt_required()
@role_required('admin', 'moderator')
def get_news_detail(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    db.session.commit()
    return jsonify({
        'id': article.id,
        'title': article.title,
        'content': article.content,
        'excerpt': article.excerpt,
        'category': article.category,
        'main_image': article.main_image,
        'is_verified': article.is_verified,
        'views_count': article.views_count,
        'read_time': article.read_time,
        'published_at': article.published_at.isoformat() + 'Z' if article.published_at else None
    }), 200

@admin_bp.route('/news', methods=['POST'])
@jwt_required()
@role_required('admin', 'moderator')
def create_news():
    data = request.get_json() or {}

    form = NewsForm(data=data)
    # if not form.validate():
    #     return jsonify({'errors': form.errors}), 400
    
    article = NewsArticle(
        title=form.title.data,
        slug=form.slug.data,
        excerpt=form.excerpt.data,
        content=form.content.data,
        category=form.category.data,
        is_verified=form.is_verified.data
    )
    # Handle image upload separately
    db.session.add(article)
    db.session.commit()

    log_action(get_jwt_identity(), 'create_news', f'Новость {article.id} создана', request.remote_addr)

    return jsonify({'message': 'Новость создана', 'id': article.id}), 201

@admin_bp.route('/news/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_news(id):
    article = NewsArticle.query.get_or_404(id)
    data = request.get_json() or {}
    # Update fields
    for field in ['title', 'slug', 'excerpt', 'content', 'category', 'region', 'tags', 'is_verified']:
        if field in data:
            setattr(article, field, data[field])
    db.session.commit()

    log_action(get_jwt_identity(), 'update_news', f'Новость {article.id} обновлена', request.remote_addr)

    return jsonify({'message': 'Новость обновлена'}), 200

@admin_bp.route('/news/<int:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'moderator')
def delete_news(id):
    article = NewsArticle.query.get_or_404(id)
    db.session.delete(article)
    db.session.commit()

    log_action(get_jwt_identity(), 'delete_news', f'Новость {id} удалена', request.remote_addr)

    return jsonify({'message': 'Новость удалена'}), 200
