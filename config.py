import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'condofront')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASS = os.environ.get('DB_PASS', '')
    DB_PORT = int(os.environ.get('DB_PORT', 5432))
    SESSION_PERMANENT = False

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.urandom(24)  # random every restart is fine for dev

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig
}
