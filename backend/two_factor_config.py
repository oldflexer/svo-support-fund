"""
Конфигурация двухфакторной аутентификации
"""

class TwoFactorConfig:
    # Настройки OTP (Time-based One-Time Password)
    OTP_DIGITS = 6  # Количество цифр в токене
    OTP_INTERVAL = 30  # Интервал в секундах
    OTP_VALID_WINDOW = 1  # Допустимое окно (в интервалах)
    
    # Настройки лимитов
    MAX_LOGIN_ATTEMPTS = 5  # Максимум попыток входа
    LOGIN_TIMEOUT_MINUTES = 15  # Таймаут после превышения попыток
    TWO_FA_TOKEN_LIFETIME = 300  # Время жизни временного токена (секунды)
    
    # Настройки резервных кодов
    BACKUP_CODES_COUNT = 10  # Количество резервных кодов
    BACKUP_CODE_FORMAT = "XXXX-XXXX"  # Формат резервных кодов
    
    # Сообщения
    MESSAGES = {
        '2fa_required': 'Требуется двухфакторная аутентификация',
        '2fa_invalid_token': 'Неверный код аутентификации',
        '2fa_setup_success': '2FA успешно настроена',
        '2fa_enable_success': '2FA успешно включена',
        '2fa_disable_success': '2FA успешно отключена',
        'rate_limit_exceeded': 'Слишком много попыток. Попробуйте позже.',
        'backup_code_used': 'Использован резервный код',
        'backup_codes_regenerated': 'Резервные коды обновлены'
    }
    
    # Настройки безопасности
    REQUIRE_2FA_FOR_ADMINS = True  # Требовать 2FA для администраторов
    ALLOW_BACKUP_CODES = True  # Разрешить использование резервных кодов
    FORCE_2FA_SETUP_DAYS = 7  # Принудительная настройка 2FA через N дней после создания аккаунта
    
    @classmethod
    def get_issuer_name(cls):
        """Имя издателя для QR кода"""
        import os
        return os.environ.get('2FA_ISSUER_NAME', 'Фонд поддержки СВО')
    
    @classmethod
    def get_allowed_authenticator_apps(cls):
        """Список рекомендуемых приложений для аутентификации"""
        return [
            {'name': 'Google Authenticator', 'url': 'https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2'},
            {'name': 'Microsoft Authenticator', 'url': 'https://www.microsoft.com/ru-ru/security/mobile-authenticator-app'},
            {'name': 'Authy', 'url': 'https://authy.com/'},
            {'name': 'LastPass Authenticator', 'url': 'https://lastpass.com/auth/'}
        ]