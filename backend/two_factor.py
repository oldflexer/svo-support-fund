"""
Модуль для двухфакторной аутентификации (2FA)
"""
import qrcode
from io import BytesIO
import base64
import json
from datetime import datetime, timedelta
from flask import jsonify, request
from functools import wraps
from models import db, FailedLoginAttempt
from auth import log_audit

class TwoFactorAuth:
    """Класс для управления двухфакторной аутентификацией"""
    
    @staticmethod
    def setup_2fa(user):
        """
        Настройка 2FA для пользователя
        
        Returns:
            dict: Данные для настройки 2FA (секрет, QR код, резервные коды)
        """
        # Генерируем секрет если его нет
        if not user.two_factor_secret:
            user.generate_two_factor_secret()
        
        # Генерируем резервные коды если их нет
        if not user.two_factor_backup_codes:
            backup_codes = user.generate_backup_codes()
        else:
            backup_codes = json.loads(user.two_factor_backup_codes)
        
        # Генерируем QR код
        provisioning_uri = user.get_two_factor_provisioning_uri()
        qr_code_data = TwoFactorAuth.generate_qr_code(provisioning_uri)
        
        db.session.commit()
        
        return {
            'secret': user.two_factor_secret,
            'provisioning_uri': provisioning_uri,
            'qr_code': qr_code_data,
            'backup_codes': backup_codes
        }
    
    @staticmethod
    def generate_qr_code(provisioning_uri):
        """
        Генерация QR кода в base64
        
        Args:
            provisioning_uri: URI для настройки в аутентификаторе
            
        Returns:
            str: base64 encoded PNG изображение QR кода
        """
        # Создаём QR код
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Создаём изображение
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Конвертируем в base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_2fa_token(user, token, use_backup=False):
        """
        Проверка 2FA токена
        
        Args:
            user: Объект пользователя
            token: Введённый токен
            use_backup: Использовать ли резервный код
            
        Returns:
            bool: Успешна ли проверка
        """
        if not user.two_factor_enabled or not user.two_factor_secret:
            return True  # Если 2FA не включена, пропускаем проверку
        
        if use_backup:
            # Проверяем резервный код
            if user.verify_backup_code(token):
                log_audit('2fa_backup_used', 'user', user.id, 'Used backup code')
                db.session.commit()
                return True
            return False
        
        # Проверяем обычный OTP токен
        if user.verify_two_factor_token(token):
            user.two_factor_last_used = datetime.utcnow()
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def enable_2fa(user, token):
        """
        Включение 2FA после проверки первого токена
        
        Args:
            user: Объект пользователя
            token: Первый токен для подтверждения
            
        Returns:
            tuple: (success, message)
        """
        if user.two_factor_enabled:
            return False, "2FA уже включена"
        
        if not user.two_factor_secret:
            return False, "Сначала настройте 2FA"
        
        # Проверяем токен
        if not user.verify_two_factor_token(token):
            return False, "Неверный токен"
        
        # Включаем 2FA
        user.two_factor_enabled = True
        user.two_factor_last_used = datetime.utcnow()
        
        # Логируем действие
        log_audit('2fa_enabled', 'user', user.id, 'Enabled two-factor authentication')
        
        db.session.commit()
        return True, "2FA успешно включена"
    
    @staticmethod
    def disable_2fa(user, password=None, token=None):
        """
        Отключение 2FA
        
        Args:
            user: Объект пользователя
            password: Пароль для подтверждения (опционально)
            token: Токен 2FA (опционально)
            
        Returns:
            tuple: (success, message)
        """
        if not user.two_factor_enabled:
            return False, "2FA не включена"
        
        # Если есть пароль - проверяем его
        if password and not user.check_password(password):
            return False, "Неверный пароль"
        
        # Если требуется токен - проверяем его
        if token and not TwoFactorAuth.verify_2fa_token(user, token):
            return False, "Неверный токен 2FA"
        
        # Отключаем 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        user.two_factor_last_used = None
        
        # Логируем действие
        log_audit('2fa_disabled', 'user', user.id, 'Disabled two-factor authentication')
        
        db.session.commit()
        return True, "2FA успешно отключена"
    
    @staticmethod
    def regenerate_backup_codes(user, token):
        """
        Регенерация резервных кодов
        
        Args:
            user: Объект пользователя
            token: Токен 2FA для подтверждения
            
        Returns:
            tuple: (success, message, backup_codes)
        """
        if not user.two_factor_enabled:
            return False, "2FA не включена", None
        
        # Проверяем токен
        if not TwoFactorAuth.verify_2fa_token(user, token):
            return False, "Неверный токен", None
        
        # Генерируем новые коды
        backup_codes = user.generate_backup_codes()
        
        # Логируем действие
        log_audit('2fa_backup_regenerated', 'user', user.id, 'Regenerated backup codes')
        
        db.session.commit()
        return True, "Резервные коды обновлены", backup_codes
    
    @staticmethod
    def check_rate_limit(username, ip_address):
        """
        Проверка лимита попыток входа
        
        Args:
            username: Имя пользователя
            ip_address: IP адрес
            
        Returns:
            tuple: (allowed, wait_time_seconds)
        """
        # Лимиты: максимум 5 попыток за 15 минут
        time_threshold = datetime.utcnow() - timedelta(minutes=15)
        
        # Подсчитываем попытки по IP
        ip_attempts = FailedLoginAttempt.query.filter(
            FailedLoginAttempt.ip_address == ip_address,
            FailedLoginAttempt.attempted_at >= time_threshold
        ).count()
        
        # Подсчитываем попытки по username
        user_attempts = FailedLoginAttempt.query.filter(
            FailedLoginAttempt.username == username,
            FailedLoginAttempt.attempted_at >= time_threshold
        ).count()
        
        max_attempts = 5
        
        if ip_attempts >= max_attempts or user_attempts >= max_attempts:
            # Находим самую старую попытку в пределах окна
            oldest_attempt = FailedLoginAttempt.query.filter(
                FailedLoginAttempt.ip_address == ip_address,
                FailedLoginAttempt.attempted_at >= time_threshold
            ).order_by(FailedLoginAttempt.attempted_at).first()
            
            if oldest_attempt:
                wait_until = oldest_attempt.attempted_at + timedelta(minutes=15)
                wait_seconds = (wait_until - datetime.utcnow()).total_seconds()
                return False, max(0, int(wait_seconds))
        
        return True, 0
    
    @staticmethod
    def record_failed_attempt(username, admin_id=None, reason='wrong_password'):
        """
        Запись неудачной попытки входа
        
        Args:
            username: Имя пользователя
            admin_id: ID администратора (если известен)
            reason: Причина неудачи
        """
        attempt = FailedLoginAttempt(
            username=username,
            admin_id=admin_id,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            reason=reason
        )
        
        db.session.add(attempt)
        db.session.commit()
    
    @staticmethod
    def clear_failed_attempts(username):
        """
        Очистка неудачных попыток после успешного входа
        
        Args:
            username: Имя пользователя
        """
        FailedLoginAttempt.query.filter_by(username=username).delete()
        db.session.commit()

# Декораторы для защиты маршрутов 2FA
def require_2fa_setup(f):
    """Декоратор требует настройки 2FA (но не обязательно включения)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({
                'success': False,
                'message': 'Требуется аутентификация'
            }), 401
        
        user = request.current_user
        
        # Если 2FA уже настроена, возвращаем информацию
        if user.two_factor_secret:
            return jsonify({
                'success': False,
                'message': '2FA уже настроена',
                'two_factor_enabled': user.two_factor_enabled
            }), 400
        
        return f(*args, **kwargs)
    return decorated_function

def require_2fa_enabled(f):
    """Декоратор требует включенной 2FA"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({
                'success': False,
                'message': 'Требуется аутентификация'
            }), 401
        
        user = request.current_user
        
        if not user.two_factor_enabled:
            return jsonify({
                'success': False,
                'message': '2FA не включена. Сначала включите двухфакторную аутентификацию.'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function