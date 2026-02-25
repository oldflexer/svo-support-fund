from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import pyotp
import secrets
import json

db = SQLAlchemy()
bcrypt = Bcrypt()

class AdminUser(db.Model):
    """System administrators"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(50), default='moderator')  # 'admin', 'moderator', 'viewer'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Two-factor authentication fields
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32))  # Secret for generating OTP
    two_factor_backup_codes = db.Column(db.Text)  # JSON list of backup codes
    two_factor_last_used = db.Column(db.DateTime)  # Time of last 2FA usage
    
    # Relationships
    login_attempts = db.relationship('FailedLoginAttempt', backref='admin', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='admin', lazy=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def generate_two_factor_secret(self):
        """Generate secret for 2FA"""
        self.two_factor_secret = pyotp.random_base32()
        return self.two_factor_secret
    
    def get_two_factor_provisioning_uri(self, issuer_name="Фонд СВО"):
        """Get URI for QR code"""
        if not self.two_factor_secret:
            self.generate_two_factor_secret()
        
        return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(
            name=self.email,
            issuer_name=issuer_name
        )
    
    def verify_two_factor_token(self, token):
        """Verify OTP token"""
        if not self.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token, valid_window=1)  # valid_window=1 allows for small time discrepancies
    
    def verify_backup_code(self, code):
        """Verify backup code"""
        if not self.two_factor_backup_codes:
            return False
        
        import json
        try:
            backup_codes = json.loads(self.two_factor_backup_codes)
            if code in backup_codes:
                # Remove used code
                backup_codes.remove(code)
                self.two_factor_backup_codes = json.dumps(backup_codes)
                return True
        except:
            pass
        
        return False
    
    def generate_backup_codes(self, count=10):
        """Generate backup codes"""
        
        
        backup_codes = []
        for _ in range(count):
            # Generate 8-digit codes with separator
            code = f"{secrets.randbelow(10000):04d}-{secrets.randbelow(10000):04d}"
            backup_codes.append(code)
        
        self.two_factor_backup_codes = json.dumps(backup_codes)
        return backup_codes
        
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'is_active': self.is_active,
            'two_factor_enabled': self.two_factor_enabled,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None,
            'last_login': self.last_login.strftime('%Y-%m-%d %H:%M:%S') if self.last_login else None
        }
    
    def to_dict_without_secrets(self):
        """Version without sensitive data"""
        data = self.to_dict()
        # Remove secrets from response
        if 'two_factor_secret' in data:
            del data['two_factor_secret']
        if 'two_factor_backup_codes' in data:
            del data['two_factor_backup_codes']
        return data
        
class FailedLoginAttempt(db.Model):
    """Failed login attempts"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(100))  # 'wrong_password', '2fa_failed', etc.

class Donation(db.Model):
    """Donations"""
    id = db.Column(db.Integer, primary_key=True)
    donor_name = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_anonymous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='waiting')  # 'waiting', 'processed', 'sent'
    
    assistance_type = db.relationship('AssistanceType', backref='donations')
    
class Volunteer(db.Model):
    """Volunteers"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    skills = db.Column(db.Text)
    city = db.Column(db.String(100))
    can_deliver = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class NewsArticle(db.Model):
    """News and frontline reports"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='news')  # news, report, summary, story
    author = db.Column(db.String(100))
    source = db.Column(db.String(200))  # Source of information
    region = db.Column(db.String(100))  # Region to which the news relates
    is_published = db.Column(db.Boolean, default=False)
    is_verified = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)  # Important news
    views_count = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    tags = db.Column(db.Text)  # JSON list of tags
    images = db.relationship('NewsImage', backref='article', lazy=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'))
    created_by = db.relationship('AdminUser', backref='news_articles')

class NewsImage(db.Model):
    """Images for news"""
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey('news_article.id'), nullable=False)
    image_url = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.String(200))
    is_main = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class AuditLog(db.Model):
    """Administrator action logs"""
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'))
    action = db.Column(db.String(100), nullable=False)  # 'login', 'create', 'update', 'delete'
    entity_type = db.Column(db.String(50))  # 'unit', 'donation', 'user', etc.
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)