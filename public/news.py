
from flask import jsonify, request
from models import NewsArticle
from . import public_bp

# -------------------------------
# API: News
# -------------------------------

@public_bp.route('/news', methods=['GET'])
def get_news():
    category = request.args.get('category', None)

    query = NewsArticle.query
    if category:
        query = query.filter_by(category=category)
    
    query = query.order_by(NewsArticle.published_at.desc()).all()
    news = [{
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
    } for a in query]
    
    return jsonify({
        'items': news
    }), 200
