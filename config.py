import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_NAME = os.environ.get('DB_NAME', 'condofront')
    DB_USER = os.environ.get('DB_USER', 'postgres')
    DB_PASS = os.environ.get('DB_PASS', '')
    SESSION_PERMANENT = False

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.urandom(24)  # random every restart

class ProductionConfig(Config):
    DEBUG = False
    SECRET_KEY = os.environ.get('SECRET_KEY')  # fixed from .env in production

config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig
}