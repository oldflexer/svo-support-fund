from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
import pyotp

db = SQLAlchemy()
bcrypt = Bcrypt()

class AdminUser(db.Model):
    """Администраторы системы"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100))
    role = db.Column(db.String(50), default='moderator')  # 'admin', 'moderator', 'viewer'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Поля для двухфакторной аутентификации
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32))  # Секрет для генерации OTP
    two_factor_backup_codes = db.Column(db.Text)  # JSON список резервных кодов
    two_factor_last_used = db.Column(db.DateTime)  # Время последнего использования 2FA
    
    # Связи
    login_attempts = db.relationship('FailedLoginAttempt', backref='admin', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='admin', lazy=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def generate_two_factor_secret(self):
        """Генерация секрета для 2FA"""
        self.two_factor_secret = pyotp.random_base32()
        return self.two_factor_secret
    
    def get_two_factor_provisioning_uri(self, issuer_name="Фонд СВО"):
        """Получение URI для QR-кода"""
        if not self.two_factor_secret:
            self.generate_two_factor_secret()
        
        return pyotp.totp.TOTP(self.two_factor_secret).provisioning_uri(
            name=self.email,
            issuer_name=issuer_name
        )
    
    def verify_two_factor_token(self, token):
        """Проверка OTP токена"""
        if not self.two_factor_secret:
            return False
        
        totp = pyotp.TOTP(self.two_factor_secret)
        return totp.verify(token, valid_window=1)  # valid_window=1 позволяет небольшие расхождения во времени
    
    def verify_backup_code(self, code):
        """Проверка резервного кода"""
        if not self.two_factor_backup_codes:
            return False
        
        import json
        try:
            backup_codes = json.loads(self.two_factor_backup_codes)
            if code in backup_codes:
                # Удаляем использованный код
                backup_codes.remove(code)
                self.two_factor_backup_codes = json.dumps(backup_codes)
                return True
        except:
            pass
        
        return False
    
    def generate_backup_codes(self, count=10):
        """Генерация резервных кодов"""
        import secrets
        import json
        
        backup_codes = []
        for _ in range(count):
            # Генерируем 8-значные коды с разделителем
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
        """Версия без чувствительных данных"""
        data = self.to_dict()
        # Убираем секреты из ответа
        if 'two_factor_secret' in data:
            del data['two_factor_secret']
        if 'two_factor_backup_codes' in data:
            del data['two_factor_backup_codes']
        return data
        
class FailedLoginAttempt(db.Model):
    """Неудачные попытки входа"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80))
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    attempted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reason = db.Column(db.String(100))  # 'wrong_password', '2fa_failed', etc.
        
class Fighter(db.Model):
    """Боец/участник СВО"""
    id = db.Column(db.Integer, primary_key=True)
    call_sign = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(200))
    region = db.Column(db.String(100))
    status = db.Column(db.String(50))  # 'активный', 'ранен', 'на лечении'
    needs = db.Column(db.Text)  # JSON строка с потребностями
    story = db.Column(db.Text)
    photo_url = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_verified = db.Column(db.Boolean, default=False)
    priority = db.Column(db.Integer, default=1)  # 1-высокий, 2-средний, 3-низкий
    
    donations = db.relationship('Donation', backref='fighter', lazy=True)

class AssistanceType(db.Model):
    """Типы помощи"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(50))
    category = db.Column(db.String(50))  # 'медицина', 'техника', 'снаряжение', 'прочее'

class Donation(db.Model):
    """Пожертвования"""
    id = db.Column(db.Integer, primary_key=True)
    donor_name = db.Column(db.String(100))
    amount = db.Column(db.Float, nullable=False)
    fighter_id = db.Column(db.Integer, db.ForeignKey('fighter.id'))
    assistance_type_id = db.Column(db.Integer, db.ForeignKey('assistance_type.id'))
    message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_anonymous = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='ожидает')  # 'ожидает', 'обработано', 'отправлено'
    
    assistance_type = db.relationship('AssistanceType', backref='donations')

class EquipmentRequest(db.Model):
    """Запросы на снаряжение"""
    id = db.Column(db.Integer, primary_key=True)
    fighter_id = db.Column(db.Integer, db.ForeignKey('fighter.id'), nullable=False)
    item_name = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    urgency = db.Column(db.String(50))  # 'критично', 'срочно', 'обычно'
    status = db.Column(db.String(50), default='требуется')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Volunteer(db.Model):
    """Волонтеры"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    skills = db.Column(db.Text)
    city = db.Column(db.String(100))
    can_deliver = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)

class Delivery(db.Model):
    """Доставки помощи"""
    id = db.Column(db.Integer, primary_key=True)
    volunteer_id = db.Column(db.Integer, db.ForeignKey('volunteer.id'))
    destination = db.Column(db.String(300))
    status = db.Column(db.String(50), default='планируется')
    departure_date = db.Column(db.DateTime)
    estimated_arrival = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
class AuditLog(db.Model):
    """Лог действий администраторов"""
    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admin_user.id'))
    action = db.Column(db.String(100), nullable=False)  # 'login', 'create', 'update', 'delete'
    entity_type = db.Column(db.String(50))  # 'fighter', 'donation', 'user', etc.
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)