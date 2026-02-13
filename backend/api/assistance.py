"""
Assistance Types API endpoints
"""

from flask import Blueprint, request, jsonify, current_app
from flask_cors import cross_origin
from models import AssistanceType

assistance_bp = Blueprint('assistance', __name__)

@assistance_bp.route('/api/assistance/types', methods=['GET'])
@cross_origin()
def get_assistance_types():
    """Get all assistance types"""
    try:
        types = AssistanceType.query.all()
        
        results = []
        for type in types:
            results.append({
                'id': type.id,
                'name': type.name,
                'description': type.description,
                'icon': type.icon,
                'category': type.category
            })
        
        return jsonify({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error getting assistance types: {str(e)}'
        }), 500