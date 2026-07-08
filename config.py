import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Railway uses PG* variables, local dev uses DB_*
    DB_HOST = os.environ.get('PGHOST') or os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('PGDATABASE') or os.environ.get('DB_NAME', 'condofront')
    DB_USER = os.environ.get('PGUSER') or os.environ.get('DB_USER', 'postgres')
    DB_PASS = os.environ.get('PGPASSWORD') or os.environ.get('DB_PASS', '')
    DB_PORT = int(os.environ.get('PGPORT') or os.environ.get('DB_PORT', 5432))
    SESSION_PERMANENT = False
    REMEMBER_COOKIE_DURATION = 30  # days

    # Email — SMTP SSL port 465 (works on Railway, no port blocking)
    SMTP_HOST        = os.environ.get('SMTP_HOST', 'mail.ijsiam.com')
    SMTP_PORT        = int(os.environ.get('SMTP_PORT', 465))
    SMTP_USER        = os.environ.get('SMTP_USER', 'dashboard@ijsiam.com')
    SMTP_PASS        = os.environ.get('SMTP_PASS', '')
    MAIL_FROM        = os.environ.get('MAIL_FROM', 'CondoFront <dashboard@ijsiam.com>')
    CONTACT_TO_EMAIL = os.environ.get('CONTACT_TO_EMAIL', 'sani3878@yahoo.com')

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.urandom(24)

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig
}
