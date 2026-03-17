
from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, NewsArticle, NewsImage
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

    pagination = query.order_by(NewsArticle.published_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    items = [{
        'id': a.id,
        'title': a.title,
        'slug': a.slug,
        'excerpt': a.excerpt,
        'category': a.category,
        'main_image': a.main_image,
        'images': [{'id': img.id, 'url': img.image_url, 'position': img.position} for img in a.images],
        'is_verified': a.is_verified,
        'views_count': a.views_count,
        'read_time': a.read_time,
        'published_at': a.published_at.isoformat() + 'Z' if a.published_at else None
    } for a in pagination.items]

    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@admin_bp.route('/news', methods=['POST'])
@jwt_required()
@role_required('admin', 'moderator')
def create_news():
    data = request.get_json() or {}
    form = NewsForm(data=data, meta={'csrf': False})
    if not form.validate():
        return jsonify({'errors': form.errors}), 400

    article = NewsArticle(
        title=form.title.data,
        slug=form.slug.data,
        excerpt=form.excerpt.data,
        content=form.content.data,
        category=form.category.data,
        main_image=form.main_image.data,
        is_verified=form.is_verified.data
    )
    db.session.add(article)
    db.session.flush()  # чтобы получить id

    # Добавляем дополнительные изображения
    additional_images = data.get('additional_images', [])
    for idx, url in enumerate(additional_images):
        img = NewsImage(news_id=article.id, image_url=url, position=idx)
        db.session.add(img)

    db.session.commit()
    log_action(get_jwt_identity(), 'create_news', f'Новость {article.id} создана', request.remote_addr)
    return jsonify({'message': 'Новость создана', 'id': article.id}), 201

@admin_bp.route('/news/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'moderator')
def update_news(id):
    article = NewsArticle.query.get_or_404(id)
    data = request.get_json() or {}

    for field in ['title', 'slug', 'excerpt', 'content', 'category', 'main_image', 'is_verified']:
        if field in data:
            setattr(article, field, data[field])

    if 'additional_images' in data:
        new_urls = data['additional_images']

        existing = {img.image_url: img for img in article.images}
        for url in new_urls:
            if url in existing:
                existing[url].position = new_urls.index(url)
            else:
                img = NewsImage(news_id=article.id, image_url=url, position=new_urls.index(url))
                db.session.add(img)

        for img in article.images:
            if img.image_url not in new_urls:
                db.session.delete(img)

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

@admin_bp.route('/news/<int:id>/images/<int:image_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'moderator')
def delete_news_image(id, image_id):
    image = NewsImage.query.get_or_404(image_id)
    if image.news_id != id:
        return jsonify({'error': 'Изображение не принадлежит этой новости'}), 400
    db.session.delete(image)
    db.session.commit()
    log_action(get_jwt_identity(), 'delete_news_image', f'Изображение {image_id} удалено из новости {id}', request.remote_addr)
    return jsonify({'message': 'Изображение удалено'}), 200
