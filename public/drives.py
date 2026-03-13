
from flask import jsonify, request, current_app
from models import Drive
from . import public_bp

# -------------------------------
# API: Drives
# -------------------------------

@public_bp.route('/drives', methods=['GET'])
def get_drives():
    status = request.args.get('status', None)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', current_app.config.get('ITEMS_PER_PAGE', 20), type=int)


    query = Drive.query
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(Drive.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    drives = [{
        'id': d.id,
        'title': d.title,
        'description': d.description,
        'needs': d.needs_list,
        'status': d.status,
        'collected': d.collected,
        'needed': d.needed,
        'progress': d.progress_percentage
    } for d in pagination.items]

    return jsonify({
        'items': drives,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200
