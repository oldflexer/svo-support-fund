# Import and register modules
from flask import Flask
from backend.api.public import public_bp
from backend.api.auth import auth_bp
from backend.api.admin import admin_bp
from backend.api.admin_extended import admin_extended_bp
from backend.api.admin_donations import admin_donations_bp
from backend.api.admin_users import admin_users_bp
from backend.api.admin_audit import admin_audit_bp
from backend.api.assistance import assistance_bp
from backend.api.stats import stats_bp

app = Flask(__name__)
app.config.from_object('backend.config.Config')

# Register all admin blueprints with sub-prefixes
from backend.api import register_admin_blueprints
register_admin_blueprints(app)

# Register public and auth blueprints
from backend.api import register_public_blueprints
register_public_blueprints(app)

app.register_blueprint(public_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(admin_extended_bp, url_prefix='/api/admin')
app.register_blueprint(admin_donations_bp, url_prefix='/api/admin')
app.register_blueprint(admin_users_bp, url_prefix='/api/admin')
app.register_blueprint(admin_audit_bp, url_prefix='/api/admin')
app.register_blueprint(assistance_bp, url_prefix='/api')
app.register_blueprint(stats_bp, url_prefix='/api')


