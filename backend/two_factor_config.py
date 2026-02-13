"""
Configuration of two-factor authentication
"""

class TwoFactorConfig:
    # OTP (Time-based One-Time Password) settings
    OTP_DIGITS = 6  # Number of digits in the token
    OTP_INTERVAL = 30  # Interval in seconds
    OTP_VALID_WINDOW = 1  # Valid window (in intervals)
    
    # Limits settings
    MAX_LOGIN_ATTEMPTS = 5  # Maximum login attempts
    LOGIN_TIMEOUT_MINUTES = 15  # Timeout after exceeding attempts
    TWO_FA_TOKEN_LIFETIME = 300  # Temporary token lifetime (seconds)

    # Backup codes settings
    BACKUP_CODES_COUNT = 10  # Number of backup codes
    BACKUP_CODE_FORMAT = "XXXX-XXXX"  # Backup code format

    # Messages
    MESSAGES = {
        '2fa_required': 'Two-factor authentication is required',
        '2fa_invalid_token': 'Invalid authentication code',
        '2fa_setup_success': '2FA successfully configured',
        '2fa_enable_success': '2FA successfully enabled',
        '2fa_disable_success': '2FA successfully disabled',
        'rate_limit_exceeded': 'Too many attempts. Try again later.',
        'backup_code_used': 'Backup code used',
        'backup_codes_regenerated': 'Backup codes regenerated'
    }

    # Security settings
    REQUIRE_2FA_FOR_ADMINS = True  # Require 2FA for administrators
    ALLOW_BACKUP_CODES = True  # Allow backup codes usage
    FORCE_2FA_SETUP_DAYS = 7  # Force 2FA setup after N days of account creation
    @classmethod
    def get_issuer_name(cls):
        """Issuer name for QR code"""
        import os
        return os.environ.get('2FA_ISSUER_NAME', 'Фонд поддержки СВО')
    
    @classmethod
    def get_allowed_authenticator_apps(cls):
        """List of recommended authentication apps"""
        return [
            {'name': 'Google Authenticator', 'url': 'https://play.google.com/store/apps/details?id=com.google.android.apps.authenticator2'},
            {'name': 'Microsoft Authenticator', 'url': 'https://www.microsoft.com/ru-ru/security/mobile-authenticator-app'},
            {'name': 'Authy', 'url': 'https://authy.com/'},
            {'name': 'LastPass Authenticator', 'url': 'https://lastpass.com/auth/'}
        ]