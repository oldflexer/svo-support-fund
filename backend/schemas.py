from functools import wraps
from marshmallow import Schema, fields, validate, ValidationError, post_load
from datetime import datetime
import re

# Базовый класс для всех схем
class BaseSchema(Schema):
    class Meta:
        ordered = True  # Сохраняем порядок полей

# ==================== АУТЕНТИФИКАЦИЯ ====================

class LoginSchema(BaseSchema):
    """Схема для авторизации"""
    username = fields.Str(
        required=True,
        validate=validate.Length(min=3, max=80),
        error_messages={
            'required': 'Имя пользователя обязательно',
            'invalid': 'Неверный формат имени пользователя'
        }
    )
    password = fields.Str(
        required=True,
        validate=validate.Length(min=1),
        error_messages={
            'required': 'Пароль обязателен'
        }
    )

class RefreshTokenSchema(BaseSchema):
    """Схема для обновления токена"""
    refresh_token = fields.Str(
        required=True,
        error_messages={
            'required': 'Refresh токен обязателен'
        }
    )

# ==================== АДМИНИСТРАТОРЫ ====================

class AdminCreateSchema(BaseSchema):
    """Схема для создания администратора"""
    username = fields.Str(
        required=True,
        validate=[
            validate.Length(min=3, max=80),
            validate.Regexp(r'^[a-zA-Z0-9_]+$', error='Логин должен содержать только латинские буквы, цифры и подчёркивание')
        ],
        error_messages={
            'required': 'Логин обязателен',
            'invalid': 'Неверный формат логина'
        }
    )
    email = fields.Email(
        required=True,
        validate=validate.Length(max=120),
        error_messages={
            'required': 'Email обязателен',
            'invalid': 'Неверный формат email'
        }
    )
    password = fields.Str(
        required=True,
        validate=[
            validate.Length(min=8, max=200),
            validate.Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)', 
                          error='Пароль должен содержать хотя бы одну заглавную букву, одну строчную букву и одну цифру')
        ],
        error_messages={
            'required': 'Пароль обязателен',
            'invalid': 'Пароль не соответствует требованиям безопасности'
        }
    )
    full_name = fields.Str(
        required=False,
        validate=validate.Length(max=100),
        missing=''
    )
    role = fields.Str(
        required=False,
        validate=validate.OneOf(['admin', 'moderator', 'viewer']),
        missing='moderator'
    )
    is_active = fields.Boolean(
        required=False,
        missing=True
    )

class AdminUpdateSchema(BaseSchema):
    """Схема для обновления администратора"""
    username = fields.Str(
        required=False,
        validate=[
            validate.Length(min=3, max=80),
            validate.Regexp(r'^[a-zA-Z0-9_]+$', error='Логин должен содержать только латинские буквы, цифры и подчёркивание')
        ]
    )
    email = fields.Email(
        required=False,
        validate=validate.Length(max=120)
    )
    full_name = fields.Str(
        required=False,
        validate=validate.Length(max=100)
    )
    role = fields.Str(
        required=False,
        validate=validate.OneOf(['admin', 'moderator', 'viewer'])
    )
    is_active = fields.Boolean(required=False)
    password = fields.Str(
        required=False,
        validate=[
            validate.Length(min=8, max=200),
            validate.Regexp(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)',
                          error='Пароль должен содержать хотя бы одну заглавную букву, одну строчную букву и одну цифру')
        ]
    )

# ==================== БОЙЦЫ ====================

class FighterCreateSchema(BaseSchema):
    """Схема для создания бойца"""
    call_sign = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        error_messages={
            'required': 'Позывной обязателен'
        }
    )
    unit = fields.Str(
        required=False,
        validate=validate.Length(max=200),
        missing=''
    )
    region = fields.Str(
        required=False,
        validate=validate.Length(max=100),
        missing=''
    )
    status = fields.Str(
        required=False,
        validate=validate.OneOf(['активный', 'ранен', 'на лечении', 'отпуск']),
        missing='активный'
    )
    needs = fields.List(
        fields.Str(validate=validate.Length(max=500)),
        required=False,
        missing=[]
    )
    story = fields.Str(
        required=False,
        missing=''
    )
    photo_url = fields.Str(
        required=False,
        validate=[
            validate.URL(error='Неверный формат URL'),
            validate.Length(max=300)
        ],
        missing=''
    )
    is_verified = fields.Boolean(
        required=False,
        missing=False
    )
    priority = fields.Integer(
        required=False,
        validate=validate.Range(min=1, max=3),
        missing=2
    )

class FighterUpdateSchema(BaseSchema):
    """Схема для обновления бойца"""
    call_sign = fields.Str(
        required=False,
        validate=validate.Length(min=1, max=100)
    )
    unit = fields.Str(
        required=False,
        validate=validate.Length(max=200)
    )
    region = fields.Str(
        required=False,
        validate=validate.Length(max=100)
    )
    status = fields.Str(
        required=False,
        validate=validate.OneOf(['активный', 'ранен', 'на лечении', 'отпуск'])
    )
    needs = fields.List(
        fields.Str(validate=validate.Length(max=500)),
        required=False
    )
    story = fields.Str(required=False)
    photo_url = fields.Str(
        required=False,
        validate=[
            validate.URL(error='Неверный формат URL'),
            validate.Length(max=300)
        ]
    )
    is_verified = fields.Boolean(required=False)
    priority = fields.Integer(
        required=False,
        validate=validate.Range(min=1, max=3)
    )

# ==================== ПОЖЕРТВОВАНИЯ ====================

class DonationCreateSchema(BaseSchema):
    """Схема для создания пожертвования"""
    name = fields.Str(
        required=False,
        validate=validate.Length(max=100),
        missing='Анонимный благотворитель'
    )
    amount = fields.Float(
        required=True,
        validate=[
            validate.Range(min=100.0, max=1000000.0, 
                         error='Сумма должна быть от 100 до 1 000 000 рублей')
        ],
        error_messages={
            'required': 'Сумма пожертвования обязательна'
        }
    )
    fighter_id = fields.Integer(
        required=False,
        validate=validate.Range(min=1)
    )
    assistance_type_id = fields.Integer(
        required=False,
        validate=validate.Range(min=1)
    )
    message = fields.Str(
        required=False,
        validate=validate.Length(max=1000),
        missing=''
    )
    is_anonymous = fields.Boolean(
        required=False,
        missing=False
    )

class DonationUpdateStatusSchema(BaseSchema):
    """Схема для обновления статуса пожертвования"""
    status = fields.Str(
        required=True,
        validate=validate.OneOf(['ожидает', 'обработано', 'отправлено']),
        error_messages={
            'required': 'Статус обязателен'
        }
    )

# ==================== ВОЛОНТЁРЫ ====================

class VolunteerCreateSchema(BaseSchema):
    """Схема для регистрации волонтёра"""
    name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=100),
        error_messages={
            'required': 'Имя обязательно'
        }
    )
    email = fields.Email(
        required=True,
        validate=validate.Length(max=100),
        error_messages={
            'required': 'Email обязателен'
        }
    )
    phone = fields.Str(
        required=False,
        validate=validate.Regexp(r'^\+?[1-9]\d{1,14}$', 
                               error='Неверный формат телефона'),
        missing=''
    )
    skills = fields.Str(
        required=False,
        validate=validate.Length(max=1000),
        missing=''
    )
    city = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=100),
        error_messages={
            'required': 'Город обязателен'
        }
    )
    can_deliver = fields.Boolean(
        required=False,
        missing=False
    )

# ==================== ЗАПРОСЫ СНАРЯЖЕНИЯ ====================

class EquipmentRequestSchema(BaseSchema):
    """Схема для запроса снаряжения"""
    fighter_id = fields.Integer(
        required=True,
        validate=validate.Range(min=1),
        error_messages={
            'required': 'ID бойца обязателен'
        }
    )
    item_name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=200),
        error_messages={
            'required': 'Название предмета обязательно'
        }
    )
    quantity = fields.Integer(
        required=False,
        validate=validate.Range(min=1, max=1000),
        missing=1
    )
    urgency = fields.Str(
        required=False,
        validate=validate.OneOf(['критично', 'срочно', 'обычно']),
        missing='обычно'
    )

# ==================== ВАЛИДАЦИЯ ИНПУТОВ ====================

def validate_pagination_params(page, per_page):
    """Валидация параметров пагинации"""
    if page < 1:
        raise ValidationError('Номер страницы должен быть больше 0')
    if per_page < 1 or per_page > 100:
        raise ValidationError('Количество элементов на странице должно быть от 1 до 100')
    return True

def validate_date_range(start_date, end_date):
    """Валидация диапазона дат"""
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00')) if start_date else None
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00')) if end_date else None
        
        if start and end and start > end:
            raise ValidationError('Дата начала не может быть позже даты окончания')
        
        return start, end
    except ValueError:
        raise ValidationError('Неверный формат даты. Используйте формат YYYY-MM-DD')

def sanitize_input(text, max_length=None):
    """Очистка входных данных от потенциально опасных символов"""
    if not text:
        return text
    
    # Удаляем потенциально опасные теги
    text = re.sub(r'<[^>]*>', '', text)
    
    # Экранируем специальные символы
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    
    # Обрезаем длину если нужно
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text.strip()

# Словарь всех схем для удобного доступа
SCHEMAS = {
    'login': LoginSchema(),
    'refresh_token': RefreshTokenSchema(),
    'admin_create': AdminCreateSchema(),
    'admin_update': AdminUpdateSchema(),
    'fighter_create': FighterCreateSchema(),
    'fighter_update': FighterUpdateSchema(),
    'donation_create': DonationCreateSchema(),
    'donation_update_status': DonationUpdateStatusSchema(),
    'volunteer_create': VolunteerCreateSchema(),
    'equipment_request': EquipmentRequestSchema()
}

def validate_request_data(schema_name, data, partial=False):
    """
    Универсальная функция валидации данных запроса
    
    Args:
        schema_name: имя схемы из словаря SCHEMAS
        data: данные для валидации
        partial: разрешить частичную валидацию (для обновлений)
    
    Returns:
        dict: валидированные и очищенные данные
    """
    if schema_name not in SCHEMAS:
        raise ValidationError(f"Неизвестная схема: {schema_name}")
    
    schema = SCHEMAS[schema_name]
    
    # Очищаем строковые поля перед валидацией
    if data:
        data = sanitize_data(data, schema)
    
    try:
        # Валидируем данные
        validated_data = schema.load(data, partial=partial)
        return validated_data
    except ValidationError as err:
        # Форматируем ошибки для удобного отображения
        formatted_errors = format_validation_errors(err.messages)
        raise ValidationError(formatted_errors)

def sanitize_data(data, schema):
    """Рекурсивная очистка данных"""
    if isinstance(data, dict):
        return {k: sanitize_data(v, schema) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item, schema) for item in data]
    elif isinstance(data, str):
        # Определяем максимальную длину из схемы
        field = schema.fields.get('field_name', None)  # Нужно передавать имя поля
        max_length = None
        if hasattr(field, 'validate'):
            for validator in field.validate:
                if isinstance(validator, validate.Length):
                    max_length = validator.max
                    break
        return sanitize_input(data, max_length)
    else:
        return data

def format_validation_errors(errors):
    """Форматирование ошибок валидации для ответа API"""
    formatted = {}
    for field, messages in errors.items():
        if isinstance(messages, list):
            formatted[field] = messages[0]  # Берём первую ошибку
        elif isinstance(messages, dict):
            formatted[field] = format_validation_errors(messages)
        else:
            formatted[field] = str(messages)
    return formatted

# Декоратор для валидации запросов
def validate_request(schema_name, partial=False):
    """
    Декоратор для автоматической валидации входящих запросов
    
    Использование:
    @app.route('/api/endpoint', methods=['POST'])
    @validate_request('schema_name')
    def endpoint():
        # Данные уже валидированы и доступны в request.validated_data
        pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            from flask import request, jsonify
            
            try:
                # Получаем данные в зависимости от метода
                if request.method in ['POST', 'PUT', 'PATCH']:
                    data = request.get_json(silent=True) or {}
                else:
                    data = request.args.to_dict()
                
                # Валидируем данные
                validated_data = validate_request_data(schema_name, data, partial)
                
                # Добавляем валидированные данные в объект запроса
                request.validated_data = validated_data
                
                return func(*args, **kwargs)
                
            except ValidationError as err:
                return jsonify({
                    'success': False,
                    'message': 'Ошибка валидации данных',
                    'errors': err.messages
                }), 400
                
        return wrapper
    return decorator
    
# ==================== ДВУХФАКТОРНАЯ АУТЕНТИФИКАЦИЯ ====================

class TwoFactorSetupSchema(BaseSchema):
    """Схема для настройки 2FA (нет полей, просто подтверждение)"""
    pass

class TwoFactorVerifySchema(BaseSchema):
    """Схема для проверки 2FA токена"""
    token = fields.Str(
        required=True,
        validate=validate.Length(min=6, max=8),
        error_messages={
            'required': 'Токен обязателен'
        }
    )
    use_backup = fields.Boolean(
        required=False,
        missing=False
    )

class TwoFactorEnableSchema(BaseSchema):
    """Схема для включения 2FA"""
    token = fields.Str(
        required=True,
        validate=validate.Length(min=6, max=8),
        error_messages={
            'required': 'Токен обязателен'
        }
    )

class TwoFactorDisableSchema(BaseSchema):
    """Схема для отключения 2FA"""
    password = fields.Str(
        required=False,
        validate=validate.Length(min=1)
    )
    token = fields.Str(
        required=False,
        validate=validate.Length(min=6, max=8)
    )

class TwoFactorRegenerateBackupSchema(BaseSchema):
    """Схема для регенерации резервных кодов"""
    token = fields.Str(
        required=True,
        validate=validate.Length(min=6, max=8),
        error_messages={
            'required': 'Токен обязателен'
        }
    )

# Обновляем словарь SCHEMAS
SCHEMAS.update({
    'two_factor_setup': TwoFactorSetupSchema(),
    'two_factor_verify': TwoFactorVerifySchema(),
    'two_factor_enable': TwoFactorEnableSchema(),
    'two_factor_disable': TwoFactorDisableSchema(),
    'two_factor_regenerate_backup': TwoFactorRegenerateBackupSchema()
})