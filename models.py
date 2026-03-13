from datetime import datetime, UTC
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='moderator')  # admin, moderator
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    last_login = db.Column(db.DateTime)
    
    # 2FA
    totp_secret = db.Column(db.String(32), nullable=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.Text, nullable=True)  # JSON list
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, perm):
        if self.role == 'admin':
            return True
        # Add more granular permissions if needed
        return False

class Donation(db.Model):
    __tablename__ = 'donations'
    
    id = db.Column(db.Integer, primary_key=True)
    donor_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # in rubles
    message = db.Column(db.Text)
    is_anonymous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='ожидает')  # ожидает, обработано, отправлено
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    # Optional link to a specific drive
    drive_id = db.Column(db.Integer, db.ForeignKey('drives.id'), nullable=True)

class Drive(db.Model):
    __tablename__ = 'drives'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    needs = db.Column(db.Text)  # JSON list
    status = db.Column(db.String(20), default='активен')  # активен, завершен, приостановлен
    collected = db.Column(db.Integer, default=0)
    needed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    
    @property
    def progress_percentage(self):
        if self.needed == 0:
            return 0
        return min(100, int((self.collected / self.needed) * 100))
    
    @property
    def needs_list(self):
        import json
        try:
            return json.loads(self.needs)
        except:
            return []

class NewsArticle(db.Model):
    __tablename__ = 'news'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    excerpt = db.Column(db.Text)
    content = db.Column(db.Text)
    category = db.Column(db.String(50), default='новости')  # новости, отчёт, история
    main_image = db.Column(db.String(500))
    is_verified = db.Column(db.Boolean, default=False)
    views_count = db.Column(db.Integer, default=0)
    published_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))
    
    @property
    def read_time(self):
        # rough estimate: 200 words per minute
        word_count = len(self.content.split()) if self.content else 0
        return max(1, round(word_count / 200))

class Volunteer(db.Model):
    __tablename__ = 'volunteers'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20))
    city = db.Column(db.String(100))
    skills = db.Column(db.Text)
    can_deliver = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='новый')  # новый, связались, активен, архив
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))

class Setting(db.Model):
    __tablename__ = 'settings'
    
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), onupdate=lambda: datetime.now(UTC).replace(tzinfo=None))

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(64))
    action = db.Column(db.String(200))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None))