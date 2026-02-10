# File utilities

def get_file_extension(filename):
    """Get file extension from filename"""
    return filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
def is_allowed_file(filename, allowed_extensions=None):
    """Check if file has allowed extension"""
    if allowed_extensions is None:
        allowed_extensions = ['jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx']
    
    return '.' in filename and \ 
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Random utilities
def generate_random_string(length=8):
    """Generate random alphanumeric string"""
    import random
    import string
    
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

def generate_token():
    """Generate secure random token"""
    import secrets
    return secrets.token_urlsafe(32)

# Password utilities
def hash_password(password):
    """Hash password using bcrypt"""
    import bcrypt
    
    if not password:
        return None
    
    # Generate salt and hash password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def check_password(stored_password, provided_password):
    """Check if provided password matches stored hash"""
    import bcrypt
    
    if not stored_password or not provided_password:
        return False
    
    try:
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))
    except:
        return False

# IP utilities
def get_client_ip(request):
    """Get client IP address from request"""
    if request.headers.getlist('X-Forwarded-For'):
        ip = request.headers.getlist('X-Forwarded-For')[0]
    elif request.headers.get('X-Real-IP'):
        ip = request.headers.get('X-Real-IP')
    else:
        ip = request.remote_addr
    
    return ip

# Logging utilities
def create_audit_log(admin_id, action, entity_type, entity_id):
    """Create audit log entry"""
    from backend.models import AuditLog
    
    audit_log = AuditLog(
        admin_id=admin_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id
    )
    
    from backend import db
    db.session.add(audit_log)
    db.session.commit()
    return audit_log

# Data utilities
def clean_data(data):
    """Clean and sanitize input data"""
    if isinstance(data, dict):
        return {k: clean_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data(item) for item in data]
    elif isinstance(data, str):
        return data.strip()
    else:
        return data

def dict_to_object(data, obj):
    """Convert dictionary to object attributes"""
    for key, value in data.items():
        if hasattr(obj, key):
            setattr(obj, key, value)
    return obj
