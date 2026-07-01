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

    # SMTP — provider-agnostic, swap via env vars only
    # Gmail:   SMTP_HOST=smtp.gmail.com    SMTP_PORT=587
    # Outlook: SMTP_HOST=smtp.office365.com SMTP_PORT=587
    SMTP_HOST = os.environ.get('SMTP_HOST',  'mail.ijsiam.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', 'dashboard@ijsiam.com')
    SMTP_PASS = os.environ.get('EMAIL_PASS', 'Email3878@786')
    CONTACT_TO_EMAIL = os.environ.get('CONTACT_TO_EMAIL', 'dashboard@ijsiam.com')

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
