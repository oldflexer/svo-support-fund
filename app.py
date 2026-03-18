import os

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from dotenv import load_dotenv
from vite_helpers import vite_asset

from config import config
from models import db, User
from public import public_bp
from admin import admin_bp
from auth import auth_bp

# -------------------------------
# Initialize
# -------------------------------

# Load .env
# load_dotenv()

# Create Flask app
app = Flask(__name__, static_folder='static', template_folder='templates')
env = os.environ.get('FLASK_ENV', 'default')
app.config.from_object(config[env])
db.init_app(app)

# Initialize extensions
CORS(app)
jwt = JWTManager(app)
migrate = Migrate(app, db)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
with app.app_context():
    db.create_all()

    # Create admin if not exists
    if not User.query.filter_by(username='admin').first():
        administrator = User(
            username='admin',
            email='admin@example.com',
            full_name='Administrator',
            role='admin',
            is_active=True
        )
        administrator.set_password('Admin123!')

        db.session.add(administrator)
        
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

@app.context_processor
def utility_processor():
    return dict(vite_asset=vite_asset)

# -------------------------------
# Frontend routes
# -------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/static/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# -------------------------------
# API: Public
# -------------------------------

app.register_blueprint(public_bp)

# -------------------------------
# API: Admin
# -------------------------------

app.register_blueprint(admin_bp)

# -------------------------------
# API: Auth
# -------------------------------

app.register_blueprint(auth_bp)

# -------------------------------
# App run
# -------------------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
