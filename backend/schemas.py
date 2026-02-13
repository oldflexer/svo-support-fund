from functools import wraps
from flask import request, jsonify
from schemas import validate_request_data, ValidationError

def validate_json(schema_name):
    """
    Middleware for validating JSON data
    
    Args:
        schema_name: name of the schema from schemas.py
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Check Content-Type
            if not request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Content-Type must be application/json'
                }), 400
            
            # Get JSON data
            data = request.get_json(silent=True)
            if data is None:
                return jsonify({
                    'success': False,
                    'message': 'Invalid JSON'
                }), 400
            
            try:
                # Validate data
                validated_data = validate_request_data(schema_name, data)
                
                # Save validated data in request
                request.validated_data = validated_data
                
            except ValidationError as err:
                return jsonify({
                    'success': False,
                    'message': 'Data validation error',
                    'errors': err.messages
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_query_params(schema_name):
    """
    Middleware for validating query parameters
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
                    'message': 'Query parameters validation error',
                    'errors': err.messages
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def sanitize_data(data, schema):
    """Recursive data sanitization"""
    if isinstance(data, dict):
        return {k: sanitize_data(v, schema) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item, schema) for item in data]
    elif isinstance(data, str):
        # Determine maximum length from schema
        field = schema.fields.get(k, None)  # Fixed to k
        max_length = None
        if hasattr(field, 'validate'):
            for validator in field.validate:
                if isinstance(validator, validate.Length):
                    max_length = validator.max
                    break
        return sanitize_input(data, max_length)
    else:
        return data
