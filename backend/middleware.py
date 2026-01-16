from functools import wraps
from flask import request, jsonify
from schemas import validate_request_data, ValidationError

def validate_json(schema_name):
    """
    Middleware для валидации JSON данных
    
    Args:
        schema_name: имя схемы из schemas.py
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Проверяем Content-Type
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Content-Type должен быть application/json'
                }), 400
            
            # Получаем JSON данные
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({
                    'success': False,
                    'message': 'Невалидный JSON'
                }), 400
            
            try:
                # Валидируем данные
                validated_data = validate_request_data(schema_name, data)
                
                # Сохраняем валидированные данные в request
                request.validated_data = validated_data
                
            except ValidationError as err:
                return jsonify({
                    'success': False,
                    'message': 'Ошибка валидации данных',
                    'errors': err.messages
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_query_params(schema_name):
    """
    Middleware для валидации query параметров
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.args.to_dict()
            
            try:
                validated_data = validate_request_data(schema_name, data)
                request.validated_query = validated_data
            except ValidationError as err:
                return jsonify({
                    'success': False,
                    'message': 'Ошибка валидации query параметров',
                    'errors': err.messages
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator