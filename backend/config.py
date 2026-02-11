import datetime
import os
import logging

class Config:
    # Validate required environment variables
    if not os.environ.get('SECRET_KEY'):
        logging.warning('SECRET_KEY not set, using development key')
    
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-svo-fund'
    
    # Validate database URL
    if not os.environ.get('DATABASE_URL'):
        logging.warning('DATABASE_URL not set, using SQLite for development')
    
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///svo_fund.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Security enhancements
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or 'jwt-super-secret-key-change-in-production'
    if JWT_SECRET_KEY == 'jwt-super-secret-key-change-in-production':
        logging.warning('JWT_SECRET_KEY using default value - CHANGE IN PRODUCTION!')
    
    # Upload settings
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # JWT settings
    JWT_ACCESS_TOKEN_EXPIRES = datetime.timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = datetime.timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'
    JWT_COOKIE_SECURE = True  # Only HTTPS
    JWT_COOKIE_HTTPONLY = True  # Inaccessible via JavaScript
    JWT_COOKIE_SAMESITE = 'Strict'
    
    # Rate limiting
    RATELIMIT_DEFAULT = '200 per day; 50 per hour'
    RATELIMIT_HEADERS_ENABLED = True
    RATELIMIT_SWALLOW_ERRORS = False
    
    # CORS settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', 'http://localhost:3000')
    CORS_SUPPORTS_CREDENTIALS = True
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    }