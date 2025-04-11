import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    MONGO_URI = os.environ.get('MONGO_URI')
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    CORS_ORIGINS = os.environ.get('ALLOWED_ORIGINS', '').split(',')
    PROPAGATE_EXCEPTIONS = True

class ProductionConfig(Config):
    MONGO_URI = os.environ.get('PROD_MONGO_URI')
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    MONGO_URI = os.environ.get('DEV_MONGO_URI')
    DEBUG = True

class TestingConfig(Config):
    MONGO_URI = os.environ.get('TEST_MONGO_URI')
    TESTING = True