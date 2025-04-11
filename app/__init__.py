import os
from flask import Flask, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
import cloudinary
from dotenv import load_dotenv
import logging
from logging.handlers import RotatingFileHandler

# Load environment variables first
load_dotenv()

# Extensions (initialize without app first)
mongo = PyMongo()
bcrypt = Bcrypt()
jwt = JWTManager()

def create_app(config_class=os.environ.get('FLASK_CONFIG', 'ProductionConfig')):
    app = Flask(__name__)
    
    # Configure application
    app.config.from_object(f"config.{config_class}")
    
    # Initialize extensions
    initialize_extensions(app)
    configure_cloudinary(app)
    setup_logging(app)
    register_blueprints(app)
    register_error_handlers(app)
    
    return app

def initialize_extensions(app):
    """Initialize Flask extensions"""
    mongo.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    CORS(app, supports_credentials=True, origins=os.environ.get('ALLOWED_ORIGINS', '').split(','))

def configure_cloudinary(app):
    """Configure Cloudinary with environment variables"""
    cloudinary.config(
        cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
        api_key=os.environ.get('CLOUDINARY_API_KEY'),
        api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
        secure=True
    )

def setup_logging(app):
    """Configure production logging"""
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=1024 * 1024 * 10,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Application startup')

def register_blueprints(app):
    """Register application blueprints"""
    from app.api.Music.Musicroute import musicbp
    from app.api.User.Userroute import userbp
    
    app.register_blueprint(musicbp)
    app.register_blueprint(userbp)

def register_error_handlers(app):
    """Register global error handlers"""
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Server Error: {error}")
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        app.logger.error(f"Unhandled Exception: {str(e)}")
        return jsonify(error=str(e)), 500