"""
Module for two-factor authentication (2FA)
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
    """Class for managing two-factor authentication"""
    @staticmethod
    def setup_2fa(user):
        """
        Setup 2FA for user
        Returns:
            dict: 2FA setup data (secret, QR code, backup codes)
        """
        # Generate secret if it doesn't exist
        if not user.two_factor_secret:
            user.generate_two_factor_secret()
        
        # Generate backup codes if they don't exist
        if not user.two_factor_backup_codes:
            backup_codes = user.generate_backup_codes()
        else:
            backup_codes = json.loads(user.two_factor_backup_codes)
        
        # Generate QR code
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
        Generate QR code in base64
        
        Args:
            provisioning_uri: URI for authenticator setup
            
        Returns:
            str: base64 encoded PNG image of QR code
        """
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_str}"
    
    @staticmethod
    def verify_2fa_token(user, token, use_backup=False):
        """
        Verify 2FA token
        Args:
            user: User object
            token: Entered token
            use_backup: Use backup code
        Returns:
            bool: Whether verification was successful
        """
        if not user.two_factor_enabled or not user.two_factor_secret:
            return True  # If 2FA is not enabled, skip verification
        if use_backup:
            # Check backup code
            if user.verify_backup_code(token):
                log_audit('2fa_backup_used', 'user', user.id, 'Used backup code')
                db.session.commit()
                return True
            return False
        
        # Check regular OTP token
        if user.verify_two_factor_token(token):
            user.two_factor_last_used = datetime.utcnow()
            db.session.commit()
            return True
        
        return False
    
    @staticmethod
    def enable_2fa(user, token):
        """
        Enable 2FA after verifying first token
        Args:
            user: User object
            token: First token for verification
        Returns:
            tuple: (success, message)
        """
        if user.two_factor_enabled:
            return False, "2FA is already enabled"
        
        if not user.two_factor_secret:
            return False, "Setup 2FA first"
        
        # Verify token
        if not user.verify_two_factor_token(token):
            return False, "Invalid token"
        
        # Enable 2FA
        user.two_factor_enabled = True
        user.two_factor_last_used = datetime.utcnow()
        
        # Log action
        log_audit('2fa_enabled', 'user', user.id, 'Enabled two-factor authentication')
        
        db.session.commit()
        return True, "2FA enabled successfully"
    @staticmethod
    def disable_2fa(user, password=None, token=None):
        """
        Disable 2FA
        
        Args:
            user: User object
            password: Password for confirmation (optional)
            token: 2FA token (optional)
        Returns:
            tuple: (success, message)
        """
        if not user.two_factor_enabled:
            return False, "2FA is not enabled"
        
        # If password is provided, verify it
        if password and not user.check_password(password):
            return False, "Incorrect password"
        
        # If token is required, verify it
        if token and not TwoFactorAuth.verify_2fa_token(user, token):
            return False, "Incorrect 2FA token"
        
        # Disable 2FA
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.two_factor_backup_codes = None
        user.two_factor_last_used = None
        
        # Log action
        log_audit('2fa_disabled', 'user', user.id, 'Disabled two-factor authentication')
        
        db.session.commit()
        return True, "2FA disabled successfully"
    
    @staticmethod
    def regenerate_backup_codes(user, token):
        """
        Regenerate backup codes
        Args:
            user: User object
            token: 2FA token for confirmation
        Returns:
            tuple: (success, message, backup_codes)
        """
        if not user.two_factor_enabled:
            return False, "2FA is not enabled", None
        
        # Verify token
        if not TwoFactorAuth.verify_2fa_token(user, token):
            return False, "Incorrect token", None
        
        # Generate new codes
        backup_codes = user.generate_backup_codes()
        
        # Log action
        log_audit('2fa_backup_regenerated', 'user', user.id, 'Regenerated backup codes')
        
        db.session.commit()
        return True, "Backup codes updated", backup_codes
    
    @staticmethod
    def check_rate_limit(username, ip_address):
        """
        Check login attempt rate limit
        Args:
            username: Username
            ip_address: IP address
            
        Returns:
            tuple: (allowed, wait_time_seconds)
        """
        # Limit: maximum 5 attempts within 15 minutes
        time_threshold = datetime.utcnow() - timedelta(minutes=15)
        
        # Count attempts by IP
        ip_attempts = FailedLoginAttempt.query.filter(
            FailedLoginAttempt.ip_address == ip_address,
            FailedLoginAttempt.attempted_at >= time_threshold
        ).count()
        
        # Count attempts by username
        user_attempts = FailedLoginAttempt.query.filter(
            FailedLoginAttempt.username == username,
            FailedLoginAttempt.attempted_at >= time_threshold
        ).count()
        
        max_attempts = 5
        
        if ip_attempts >= max_attempts or user_attempts >= max_attempts:
            # Find the oldest attempt within the window
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
        Record failed login attempt
        Args:
            username: Username
            admin_id: ID of administrator (if known)
            reason: Reason for failure
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
        Clear failed attempts after successful login
        Args:
            username: Username
        """
        FailedLoginAttempt.query.filter_by(username=username).delete()
        db.session.commit()

# Decorators for protecting 2FA routes
def require_2fa_setup(f):
    """Decorator requires 2FA setup (but not necessarily enabling)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({
                'success': False,
                'message': 'Authentication required'
            }), 401
        
        user = request.current_user
        
        # If 2FA is already set up, return information
        if user.two_factor_secret:
            return jsonify({
                'success': False,
                'message': '2FA is already set up',
                'two_factor_enabled': user.two_factor_enabled
            }), 400
        
        return f(*args, **kwargs)
    return decorated_function

def require_2fa_enabled(f):
    """Decorator requires enabled 2FA"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(request, 'current_user'):
            return jsonify({
                'success': False,
                'message': 'Authentication required'
            }), 401
        
        user = request.current_user
        
        if not user.two_factor_enabled:
            return jsonify({
                'success': False,
                'message': '2FA is not enabled. Enable two-factor authentication first.'
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function