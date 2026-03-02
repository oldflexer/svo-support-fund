import os
import json
import qrcode
import io
import base64
import pyotp
import secrets
from datetime import datetime, timedelta, UTC
from functools import wraps

from flask import Flask, render_template, request, jsonify, send_from_directory, session, url_for
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from werkzeug.utils import secure_filename

from config import config
from models import db, User, Donation, Volunteer, Drive, NewsArticle, Setting, AuditLog
from forms import DonationForm, VolunteerForm, DriveForm, NewsForm, LoginForm

# Create Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
env = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(config[env])

# Initialize extensions
CORS(app)
db.init_app(app)
jwt = JWTManager(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
with app.app_context():
    db.create_all()

    # Create admin if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            full_name='Administrator',
            role='admin',
            is_active=True
        )
        admin.set_password('Admin123!')
        db.session.add(admin)
        
        moderator = User(
            username='moderator',
            email='moderator@example.com',
            full_name='Moderator',
            role='moderator',
            is_active=True
        )
        moderator.set_password('Moderator123!')
        db.session.add(moderator)
        db.session.commit()
        print('Initial users created.')
    print('Database initialized.')

# -------------------------------
# Helper functions
# -------------------------------

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            current_user_id = get_jwt_identity()
            # user = session.get(current_user_id)
            user = User.query.get(current_user_id)
            if not user or not user.is_active or user.role not in roles:
                return jsonify({'error': 'Доступ запрещен'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_action(user_id, action, details='', ip=None):
    log = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip)
    db.session.add(log)
    db.session.commit()

def get_setting(key, default=None):
    setting = session.get(key)
    return setting.value if setting else default

def update_setting(key, value):
    setting = Setting.query.get(key)
    if setting:
        setting.value = value
        setting.updated_at = datetime.utcnow()
    else:
        setting = Setting(key=key, value=value)
        db.session.add(setting)
    db.session.commit()

# -------------------------------
# Frontend routes
# -------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# -------------------------------
# API: Authentication
# -------------------------------

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Логин и пароль обязательны'}), 400
    
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'error': 'Неверный логин или пароль'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Учетная запись деактивирована'}), 403
    
    # Check 2FA
    if user.two_factor_enabled:
        # Return a flag that 2FA is required
        temp_token = create_access_token(identity=user.id, additional_claims={'requires_2fa': True}, expires_delta=False)
        return jsonify({
            'requires_2fa': True,
            'temp_token': temp_token,
            'username': user.username
        }), 200
    
    # No 2FA, full login
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    log_action(user.id, 'login', 'Успешный вход', request.remote_addr)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role
        }
    }), 200

@app.route('/api/auth/verify-2fa', methods=['POST'])
def verify_2fa():
    data = request.get_json() or {}
    temp_token = data.get('temp_token')
    token = data.get('token')
    use_backup = data.get('use_backup', False)
    
    if not temp_token or not token:
        return jsonify({'error': 'Отсутствуют параметры'}), 400
    
    # Decode temp token
    try:
        from flask_jwt_extended import decode_token
        decoded = decode_token(temp_token)
        user_id = decoded['sub']
        if not decoded.get('requires_2fa'):
            return jsonify({'error': 'Неверный токен'}), 400
    except Exception as e:
        return jsonify({'error': 'Недействительный токен'}), 400
    
    user = User.query.get(user_id)
    if not user or not user.two_factor_enabled:
        return jsonify({'error': '2FA не настроена'}), 400
    
    # Verify token or backup code
    valid = False
    if use_backup and user.backup_codes:
        codes = json.loads(user.backup_codes)
        if token in codes:
            codes.remove(token)
            user.backup_codes = json.dumps(codes)
            valid = True
    else:
        if user.totp_secret:
            totp = pyotp.TOTP(user.totp_secret)
            valid = totp.verify(token)
    
    if not valid:
        return jsonify({'error': 'Неверный код'}), 400
    
    # Issue full tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    log_action(get_jwt_identity(), 'login_2fa', 'Успешный вход с 2FA', request.remote_addr)
    
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'full_name': user.full_name,
            'email': user.email,
            'role': user.role
        }
    }), 200

@app.route('/api/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    access_token = create_access_token(identity=identity)
    log_action(get_jwt_identity(), 'refresh', 'Успешно обновлен токен', request.remote_addr)
    return jsonify({'access_token': access_token}), 200

@app.route('/api/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    # Optionally blacklist token (if using blacklist)
    log_action(get_jwt_identity(), 'logout', 'Выход успешно выполнен', request.remote_addr)
    return jsonify({'message': 'Выход выполнен'}), 200

@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    return jsonify({
        'id': user.id,
        'username': user.username,
        'full_name': user.full_name,
        'email': user.email,
        'role': user.role
    }), 200

# -------------------------------
# API: 2FA management
# -------------------------------

@app.route('/api/auth/2fa/setup', methods=['POST'])
@jwt_required()
def setup_2fa():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    # Generate TOTP secret
    secret = pyotp.random_base32()
    user.totp_secret = secret
    db.session.commit()
    
    # Generate provisioning URI
    issuer = 'ЗащитимРодину'
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=issuer)
    
    # Generate QR code
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    qr_dataurl = f"data:image/png;base64,{qr_base64}"
    
    # Generate backup codes (5 random 8-digit numbers)
    backup_codes = [''.join(secrets.choice('0123456789') for _ in range(8)) for _ in range(5)]
    user.backup_codes = json.dumps(backup_codes)
    db.session.commit()

    log_action(get_jwt_identity(), 'setup_2fa', 'Установлена двухфакторная аутентификация', request.remote_addr)
    
    return jsonify({
        'qr_code': qr_dataurl,
        'secret': secret,
        'backup_codes': backup_codes
    }), 200

@app.route('/api/auth/2fa/enable', methods=['POST'])
@jwt_required()
def enable_2fa():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.totp_secret:
        return jsonify({'error': 'Сначала выполните настройку 2FA'}), 400
    
    data = request.get_json() or {}
    token = data.get('token')
    if not token:
        return jsonify({'error': 'Требуется код подтверждения'}), 400
    
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(token):
        return jsonify({'error': 'Неверный код'}), 400
    
    user.two_factor_enabled = True
    db.session.commit()
    
    log_action(get_jwt_identity(), '2fa_enable', 'Включена двухфакторная аутентификация', request.remote_addr)
    
    return jsonify({'message': '2FA успешно включена'}), 200

@app.route('/api/auth/2fa/disable', methods=['POST'])
@jwt_required()
def disable_2fa():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    data = request.get_json() or {}
    password = data.get('password')
    token = data.get('token')
    
    # Verify either password or current 2FA code
    valid = False
    if password and user.check_password(password):
        valid = True
    elif token and user.totp_secret:
        totp = pyotp.TOTP(user.totp_secret)
        valid = totp.verify(token)
    elif token and user.backup_codes:
        codes = json.loads(user.backup_codes)
        if token in codes:
            codes.remove(token)
            user.backup_codes = json.dumps(codes)
            valid = True
    
    if not valid:
        return jsonify({'error': 'Не удалось подтвердить личность'}), 400
    
    user.two_factor_enabled = False
    user.totp_secret = None
    user.backup_codes = None
    db.session.commit()
    
    log_action(get_jwt_identity(), '2fa_disable', 'Отключена двухфакторная аутентификация', request.remote_addr)
    
    return jsonify({'message': '2FA отключена'}), 200

@app.route('/api/auth/2fa/backup-codes', methods=['POST'])
@jwt_required()
def regenerate_backup_codes():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404
    
    import secrets
    backup_codes = [''.join(secrets.choice('0123456789') for _ in range(8)) for _ in range(5)]
    user.backup_codes = json.dumps(backup_codes)
    db.session.commit()
    
    log_action(get_jwt_identity(), '2fa_regenerate_backup', 'Сгенерированы новые резервные коды', request.remote_addr)
    
    return jsonify({'backup_codes': backup_codes}), 200

# -------------------------------
# API: Dashboard & Stats
# -------------------------------

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def dashboard():
    # Public stats (also used on front page)
    total_donations = Donation.query.count()
    total_amount = db.session.query(db.func.sum(Donation.amount)).scalar() or 0
    total_volunteers = Volunteer.query.count()
    total_new_donations = Donation.query.filter_by(status='ожидает').count()
    
    # Recent donations
    recent = Donation.query.order_by(Donation.created_at.desc()).limit(10).all()
    recent_list = [{
        'id': d.id,
        'donor_name': 'Аноним' if d.is_anonymous else d.donor_name,
        'amount': d.amount,
        'status': d.status,
        'created_at': d.created_at.isoformat()
    } for d in recent]

    # Change in last week
    week_ago = datetime.now(UTC) - timedelta(days=7)
    total_amount_week_ago = db.session.query(db.func.sum(Donation.amount)).filter(Donation.created_at < week_ago).scalar() or 0
    first_donation = Donation.query.order_by(Donation.created_at.asc()).first().amount or 0
    
    if total_amount_week_ago:
        change = (total_amount - total_amount_week_ago) / total_amount_week_ago
    elif first_donation:
        change = (total_amount - first_donation) / first_donation
    else:
        change = 0
    
    # For chart data (last 7 days)
    dates = []
    amounts = []
    for i in range(6, -1, -1):
        day = datetime.now(UTC) - timedelta(days=i)
        dates.append(day.strftime('%d.%m'))
        day_start = datetime.combine(day, datetime.min.time())
        day_end = datetime.combine(day, datetime.max.time())
        total = db.session.query(db.func.sum(Donation.amount)).filter(
            Donation.created_at.between(day_start, day_end)
        ).scalar() or 0
        amounts.append(total)
    
    return jsonify({
        'donations': {
            'total': total_donations,
            'total_amount': total_amount,
            'change': change,
            'total_new_donations': total_new_donations
        },
        'volunteers': {
            'total': total_volunteers
        },
        'recent_donations': recent_list,
        'chart': {
            'labels': dates,
            'datasets': [{'label': 'Сумма пожертвований', 'data': amounts}]
        }
    }), 200

# -------------------------------
# API: Donations
# -------------------------------

@app.route('/api/donations', methods=['GET'])
def get_donations():
    page = request.args.get('page', 1, type=int)
    per_page = app.config['ITEMS_PER_PAGE']
    status = request.args.get('status')
        
    query = Donation.query
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(Donation.created_at.desc()).paginate(page=page, per_page=per_page)
    
    donations = [{
        'id': d.id,
        'donor_name': 'Аноним' if d.is_anonymous else d.donor_name,
        'amount': d.amount,
        'message': d.message,
        'is_anonymous': d.is_anonymous,
        'status': d.status,
        'created_at': d.created_at.isoformat()
    } for d in pagination.items]

    return jsonify({
        'items': donations,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@app.route('/api/donations', methods=['POST'])
def create_donation():
    data = request.get_json()
    form = DonationForm(data=data)
    # if not form.validate():
    #     return jsonify({'errors': form.errors}), 400
    
    donation = Donation(
        donor_name=form.name.data,
        amount=form.amount.data,
        message=form.message.data,
        is_anonymous=form.is_anonymous.data,
        status='ожидает'
    )
    db.session.add(donation)
    db.session.commit()
    
    # Update stats (e.g., total collected)
    total = db.session.query(db.func.sum(Donation.amount)).scalar()
    update_setting('total_donated', str(total))
    
    return jsonify({'message': 'Пожертвование принято', 'id': donation.id}), 201

@app.route('/api/donations/<int:id>', methods=['PUT'])
@role_required('admin', 'moderator')
def update_donation(id):
    donation = Donation.query.get_or_404(id)
    data = request.get_json()
    if data is None:
        return jsonify({'error': 'Требуется JSON'}), 400
    if 'status' in data:
        donation.status = data['status']
        db.session.commit()

        log_action(get_jwt_identity(), 'update_donation', f'Пожертвование {donation.id} обновлено {data['status']}', request.remote_addr)

        return jsonify({'message': 'Статус обновлен'}), 200
    return jsonify({'error': 'Поле status не найдено'}), 400

# -------------------------------
# API: Volunteers
# -------------------------------

@app.route('/api/volunteers', methods=['GET'])
@jwt_required()
def get_volunteers():
    page = request.args.get('page', 1, type=int)
    per_page = app.config['ITEMS_PER_PAGE']
    status = request.args.get('status')
        
    query = Volunteer.query
    if status:
        query = query.filter_by(status=status)

    pagination = query.order_by(Volunteer.created_at.desc()).paginate(page=page, per_page=per_page)
    volunteers = [{
        'id': v.id,
        'name': v.name,
        'email': v.email,
        'phone': v.phone,
        'city': v.city,
        'skills': v.skills,
        'can_deliver': v.can_deliver,
        'status': v.status,
        'created_at': v.created_at.isoformat()
    } for v in pagination.items]
    
    return jsonify({
        'items': volunteers,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

@app.route('/api/volunteers', methods=['POST'])
def create_volunteer():
    data = request.get_json()
    form = VolunteerForm(data=data)
    # if not form.validate():
    #     return jsonify({'errors': form.errors}), 400
    
    volunteer = Volunteer(
        name=form.name.data,
        email=form.email.data,
        phone=form.phone.data,
        city=form.city.data,
        skills=form.skills.data,
        can_deliver=form.can_deliver.data,
        status='новый'
    )
    db.session.add(volunteer)
    db.session.commit()
    
    # Update volunteer count stat
    total = db.session.query(Volunteer).count()
    update_setting('total_volunteers', str(total))
    
    return jsonify({'message': 'Заявка отправлена', 'id': volunteer.id}), 201

@app.route('/api/volunteers/<int:id>', methods=['PUT'])
@role_required('admin', 'moderator')
def update_volunteer(id):
    volunteer = Volunteer.query.get_or_404(id)
    data = request.get_json() or {}
    if data is None:
        return jsonify({'error': 'Требуется JSON'}), 400
    if 'status' in data:
        volunteer.status = data['status']
        db.session.commit()

        log_action(get_jwt_identity(), 'update_volunteer', f'Волонтёр {volunteer.id} обновлен {data['status']}', request.remote_addr)

        return jsonify({'message': 'Статус обновлен'}), 200
    return jsonify({'error': 'Поле status не найдено'}), 400

# -------------------------------
# API: Drives
# -------------------------------

@app.route('/api/drives', methods=['GET'])
def get_drives():
    active_only = request.args.get('active', 'true').lower() == 'true'
    query = Drive.query
    if active_only:
        query = query.filter_by(status='активен')
    drives = query.order_by(Drive.created_at.desc()).all()
    result = [{
        'id': d.id,
        'title': d.title,
        'description': d.description,
        'needs': d.needs_list,
        'urgency': d.urgency,
        'status': d.status,
        'progress': {
            'collected': d.collected,
            'needed': d.needed,
            'percentage': d.progress_percentage
        },
        'created_at': d.created_at.isoformat()
    } for d in drives]
    return jsonify(result), 200

@app.route('/api/drives', methods=['POST'])
@role_required('admin', 'moderator')
def create_drive():
    data = request.get_json() or {}
    form = DriveForm(data=data)
    if not form.validate():
        return jsonify({'errors': form.errors}), 400
    
    drive = Drive(
        title=form.title.data,
        description=form.description.data,
        needs=form.needs.data,
        urgency=form.urgency.data,
        status=form.status.data,
        needed=form.needed.data or 0,
        collected=0
    )
    db.session.add(drive)
    db.session.commit()

    log_action(get_jwt_identity(), 'create_drive', f'Сбор {drive.id} создан', request.remote_addr)

    return jsonify({'message': 'Сбор создан', 'id': drive.id}), 201

@app.route('/api/drives/<int:id>', methods=['PUT'])
@role_required('admin', 'moderator')
def update_drive(id):
    drive = Drive.query.get_or_404(id)
    data = request.get_json() or {}
    # Update fields
    for field in ['title', 'description', 'needs', 'urgency', 'status', 'collected', 'needed']:
        if field in data:
            setattr(drive, field, data[field])
    db.session.commit()

    log_action(get_jwt_identity(), 'update_donation', f'Сбор {drive.id} обновлен {data}', request.remote_addr)

    return jsonify({'message': 'Сбор обновлен'}), 200

@app.route('/api/drives/<int:id>', methods=['DELETE'])
@role_required('admin')
def delete_drive(id):
    drive = Drive.query.get_or_404(id)
    db.session.delete(drive)
    db.session.commit()

    log_action(get_jwt_identity(), 'delete_drive', f'Сбор {drive.id} удален', request.remote_addr)

    return jsonify({'message': 'Сбор удален'}), 200

# -------------------------------
# API: News
# -------------------------------

@app.route('/api/news', methods=['GET'])
def get_news():
    category = request.args.get('category')
    query = NewsArticle.query
    if category:
        query = query.filter_by(category=category)
    news = query.order_by(NewsArticle.published_at.desc()).all()
    result = [{
        'id': a.id,
        'title': a.title,
        'slug': a.slug,
        'excerpt': a.excerpt,
        'category': a.category,
        'main_image': a.main_image,
        'is_verified': a.is_verified,
        'region': a.region,
        'tags': a.tags_list,
        'views_count': a.views_count,
        'read_time': a.read_time,
        'published_at': a.published_at.isoformat() if a.published_at else None
    } for a in news]
    return jsonify(result), 200

@app.route('/api/news/<slug>', methods=['GET'])
def get_news_detail(slug):
    article = NewsArticle.query.filter_by(slug=slug).first_or_404()
    # Increment views
    article.views_count += 1
    db.session.commit()
    return jsonify({
        'id': article.id,
        'title': article.title,
        'content': article.content,
        'excerpt': article.excerpt,
        'category': article.category,
        'main_image': article.main_image,
        'is_verified': article.is_verified,
        'region': article.region,
        'tags': article.tags_list,
        'views_count': article.views_count,
        'read_time': article.read_time,
        'published_at': article.published_at.isoformat() if article.published_at else None
    }), 200

@app.route('/api/news', methods=['POST'])
@role_required('admin', 'moderator')
def create_news():
    data = request.get_json() or {}
    form = NewsForm(data=data)
    if not form.validate():
        return jsonify({'errors': form.errors}), 400
    
    article = NewsArticle(
        title=form.title.data,
        slug=form.slug.data,
        excerpt=form.excerpt.data,
        content=form.content.data,
        category=form.category.data,
        region=form.region.data,
        tags=form.tags.data,
        is_verified=form.is_verified.data
    )
    # Handle image upload separately
    db.session.add(article)
    db.session.commit()

    log_action(get_jwt_identity(), 'create_news', f'Новость {article.id} создана', request.remote_addr)

    return jsonify({'message': 'Новость создана', 'id': article.id}), 201

@app.route('/api/news/<int:id>', methods=['PUT'])
@role_required('admin', 'moderator')
def update_news(id):
    article = NewsArticle.query.get_or_404(id)
    data = request.get_json() or {}
    # Update fields
    for field in ['title', 'slug', 'excerpt', 'content', 'category', 'region', 'tags', 'is_verified']:
        if field in data:
            setattr(article, field, data[field])
    db.session.commit()

    log_action(get_jwt_identity(), 'update_news', f'Новость {article.id} обновлена {data}', request.remote_addr)

    return jsonify({'message': 'Новость обновлена'}), 200

@app.route('/api/news/<int:id>', methods=['DELETE'])
@role_required('admin')
def delete_news(id):
    article = NewsArticle.query.get_or_404(id)
    db.session.delete(article)
    db.session.commit()

    log_action(get_jwt_identity(), 'delete_news', f'Новость {id} удалена', request.remote_addr)

    return jsonify({'message': 'Новость удалена'}), 200

# -------------------------------
# API: Image upload
# -------------------------------

@app.route('/api/upload', methods=['POST'])
@jwt_required()
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': 'Файл не найден'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Пустое имя файла'}), 400
    
    if file.filename:
        filename = secure_filename(file.filename)
        # Add timestamp to avoid collisions
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{datetime.utcnow().timestamp()}{ext}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    
        file_url = url_for('uploaded_file', filename=filename, _external=True)
        return jsonify({'url': file_url}), 200
    
    return []

# -------------------------------
# API: Admin users
# -------------------------------

@app.route('/api/admin/users', methods=['GET'])
@role_required('admin')
def get_users():
    users = User.query.all()
    result = [{
        'id': u.id,
        'username': u.username,
        'email': u.email,
        'full_name': u.full_name,
        'role': u.role,
        'is_active': u.is_active,
        'created_at': u.created_at.isoformat() if u.created_at else None,
        'last_login': u.last_login.isoformat() if u.last_login else None,
        'two_factor_enabled': u.two_factor_enabled
    } for u in users]

    log_action(get_jwt_identity(), 'get_users', f'Пользователи загружены', request.remote_addr)

    return jsonify(result), 200

@app.route('/api/admin/users', methods=['POST'])
@role_required('admin')
def create_user():
    data = request.get_json() or {}
    required = ['username', 'email', 'password', 'role']
    for field in required:
        if field not in data:
            return jsonify({'error': f'Поле {field} обязательно'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Логин уже занят'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email уже занят'}), 400
    
    user = User(
        username=data['username'],
        email=data['email'],
        full_name=data.get('full_name', ''),
        role=data['role'],
        is_active=data.get('is_active', True)
    )
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    
    log_action(get_jwt_identity(), 'create_user', f'Создан пользователь {user.id}', request.remote_addr)
    
    return jsonify({'message': 'Пользователь создан', 'id': user.id}), 201

@app.route('/api/admin/users/<int:id>', methods=['PUT'])
@jwt_required()
@role_required('admin')
def update_user(id):
    user = User.query.get_or_404(id)
    data = request.get_json() or {}
    
    # Update fields
    if 'username' in data and data['username'] != user.username:
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Логин уже занят'}), 400
        user.username = data['username']

    # if 'email' in data and data['email'] != user.email:
    #     if User.query.filter_by(email=data['email']).first():
    #         return jsonify({'error': 'Email уже занят'}), 400
    #     user.email = data['email']

    if 'email' in data:
        user.email = data['email']

    if 'full_name' in data:
        user.full_name = data['full_name']

    if 'role' in data:
        user.role = data['role']

    if 'is_active' in data:
        user.is_active = data['is_active']

    if 'password' in data and data['password']:
        user.set_password(data['password'])

    db.session.commit()
    
    log_action(get_jwt_identity(), 'update_user', f'Обновлен пользователь {user.id}', request.remote_addr)
    
    return jsonify({'message': 'Пользователь обновлен'}), 200

@app.route('/api/admin/users/<int:id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(id):
    user = User.query.get_or_404(id)
    user.is_active = not user.is_active
    db.session.commit()
    action = 'активирован' if user.is_active else 'деактивирован'

    log_action(get_jwt_identity(), f'toggle_user_{action}', f'Пользователь {user.id} {action}', request.remote_addr)
    
    return jsonify({'message': f'Пользователь {action}', 'is_active': user.is_active}), 200

@app.route('/api/admin/users/<int:id>', methods=['DELETE'])
@jwt_required()
@role_required('admin')  # только админ может удалять пользователей
def delete_user(id):
    """
    Удаление пользователя по ID.
    """
    user = User.query.get(id)
    if not user:
        return jsonify({'error': 'Пользователь не найден'}), 404

    # Нельзя удалить самого себя (опционально)
    current_user_id = get_jwt_identity()
    if user.id == current_user_id:
        return jsonify({'error': 'Нельзя удалить самого себя'}), 400

    db.session.delete(user)
    db.session.commit()

    # Логирование действия (если используется)
    log_action(get_jwt_identity(), 'delete_user', f'Удалён пользователь {id}', request.remote_addr)

    return jsonify({'message': 'Пользователь успешно удалён'}), 200

# -------------------------------
# API: Audit logs
# -------------------------------

@app.route('/api/admin/audit', methods=['GET'])
@role_required('admin')
def get_audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = app.config['ITEMS_PER_PAGE']
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page)
    logs = [{
        'id': l.id,
        'user_id': l.user_id,
        'action': l.action,
        'details': l.details,
        'ip_address': l.ip_address,
        'created_at': l.created_at.isoformat()
    } for l in pagination.items]

    log_action(get_jwt_identity(), 'get_audit_logs', f'Логи загружены', request.remote_addr)

    return jsonify({
        'items': logs,
        'total': pagination.total,
        'page': pagination.page,
        'pages': pagination.pages
    }), 200

# -------------------------------
# API: Settings
# -------------------------------

@app.route('/api/settings', methods=['GET'])
def get_settings():
    # Public settings (stats)
    total_donated = get_setting('total_donated', '0')
    total_volunteers = get_setting('total_volunteers', '0')
    return jsonify({
        'total_donated': int(total_donated),
        'total_volunteers': int(total_volunteers)
    }), 200

@app.route('/api/settings', methods=['PUT'])
@role_required('admin')
def update_settings():
    data = request.get_json() or {}
    for key, value in data.items():
        update_setting(key, str(value))

    log_action(get_jwt_identity(), 'update_settings', f'Настройки обновлены', request.remote_addr)

    return jsonify({'message': 'Настройки обновлены'}), 200

# -------------------------------
# Create initial admin user
# -------------------------------

@app.cli.command('init-db')
def init_db():
    db.create_all()
    # Create admin if not exists
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin',
            email='admin@example.com',
            full_name='Administrator',
            role='admin',
            is_active=True
        )
        admin.set_password('Admin123!')
        db.session.add(admin)
        
        moderator = User(
            username='moderator',
            email='moderator@example.com',
            full_name='Moderator',
            role='moderator',
            is_active=True
        )
        moderator.set_password('Moderator123!')
        db.session.add(moderator)
        db.session.commit()
        print('Initial users created.')
    print('Database initialized.')

if __name__ == '__main__':
    app.run(debug=True)