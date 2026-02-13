"""
API for statistics and analytics
"""

from flask import Blueprint, jsonify, request
from flask_cors import CORS
from backend.models import db
from sqlalchemy import text

# Create Blueprint
stats_bp = Blueprint('stats', __name__, url_prefix='/api')

# Enable CORS
CORS(stats_bp, supports_credentials=True)

@stats_bp.route('/overview', methods=['GET'])
def get_overview_stats():
    """Get overview statistics"""
    try:
        # Get total donations
        total_donations = db.session.execute(text(
            "SELECT COALESCE(SUM(amount), 0) FROM donation WHERE status = 'processed'"
        )).scalar()
        
        # Get total units helped
        total_units = db.session.execute(text(
            "SELECT COUNT(*) FROM unit_request WHERE status = 'completed'"
        )).scalar()
        
        # Get total volunteers
        total_volunteers = db.session.execute(text(
            "SELECT COUNT(*) FROM volunteer WHERE is_active = TRUE"
        )).scalar()
        
        # Get total assistance types
        total_assistance_types = db.session.execute(text(
            "SELECT COUNT(*) FROM assistance_type"
        )).scalar()
        
        return jsonify({
            'success': True,
            'data': {
                'total_donations': total_donations,
                'total_units': total_units,
                'total_volunteers': total_volunteers,
                'total_assistance_types': total_assistance_types
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stats_bp.route('/donations', methods=['GET'])
def get_donations_stats():
    """Get donations statistics"""
    try:
        # Get donations by month
        donations_by_month = db.session.execute(text(
            """
            SELECT 
                DATE_TRUNC('month', created_at) as month,
                SUM(amount) as total
            FROM donation 
            WHERE status = 'processed'
            GROUP BY month
            ORDER BY month
            """
        )).fetchall()
        
        # Format the data
        monthly_data = []
        for row in donations_by_month:
            month = row[0].strftime('%Y-%m')
            total = float(row[1]) if row[1] else 0
            monthly_data.append({
                'month': month,
                'total': total
            })
        
        return jsonify({
            'success': True,
            'data': {
                'monthly_data': monthly_data
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stats_bp.route('/assistance-types', methods=['GET'])
def get_assistance_types_stats():
    """Get assistance types statistics"""
    try:
        # Get assistance types with donation counts
        assistance_stats = db.session.execute(text(
            """
            SELECT 
                at.name,
                COUNT(d.id) as donation_count,
                COALESCE(SUM(d.amount), 0) as total_amount
            FROM assistance_type at
            LEFT JOIN donation d ON at.id = d.assistance_type_id AND d.status = 'processed'
            GROUP BY at.id, at.name
            ORDER BY total_amount DESC
            """
        )).fetchall()
        
        # Format the data
        assistance_data = []
        for row in assistance_stats:
            assistance_data.append({
                'name': row[0],
                'donation_count': row[1],
                'total_amount': float(row[2]) if row[2] else 0
            })
        
        return jsonify({
            'success': True,
            'data': {
                'assistance_data': assistance_data
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@stats_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for stats API"""
    try:
        # Test database connection
        db.session.execute(text('SELECT 1'))
        
        return jsonify({
            'success': True,
            'message': 'Stats API is healthy',
            'status': 'operational'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Stats API health check failed: {str(e)}',
            'status': 'degraded'
        }), 503