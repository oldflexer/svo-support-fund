
from flask import jsonify, request, current_app
from models import NewsArticle
from . import public_bp

# -------------------------------
# API: News
# -------------------------------

@public_bp.route('/news', methods=['GET'])
def get_news():
    """
    Public endpoint to retrieve news articles.
    Returns only verified articles (is_verified=True).
    Optional query parameter 'category' to filter by category.
    """
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config.get('ITEMS_PER_PAGE', 20), type=int)


    query = NewsArticle.query.filter_by(is_verified=True)
    if category:
        query = query.filter_by(category=category)

    pagination = query.order_by(NewsArticle.published_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    news_list = [{
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
    } for a in pagination.items]

    return jsonify({
        'items': news_list,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@public_bp.route('/news/<slug>', methods=['GET'])
def get_news_detail(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    return jsonify({
        'id': article.id,
        'title': article.title,
        'content': article.content,
        'excerpt': article.excerpt,
        'category': article.category,
        'main_image': article.main_image,
        'images': [{'url': img.image_url, 'position': img.position} for img in article.images],
        'is_verified': article.is_verified,
        'views_count': article.views_count,
        'read_time': article.read_time,
        'published_at': article.published_at.isoformat() + 'Z' if article.published_at else None
    }), 200
