
from flask import jsonify, request
from models import Drive
from . import public_bp

# -------------------------------
# API: Drives
# -------------------------------

@public_bp.route('/drives', methods=['GET'])
def get_drives():
    status = request.args.get('status', None)

    query = Drive.query
    if status:
        query = query.filter_by(status=status)

    drives = []
    for d in query:
        drives.append({
            'id': d.id,
            'title': d.title,
            'description': d.description,
            'needs': d.needs_list,
            'status': d.status,
            'collected': d.collected,
            'needed': d.needed,
            'progress': d.progress_percentage
        })
    
    return jsonify({
        'items': drives
    }), 200
