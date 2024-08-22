from flask import Flask, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager
import cloudinary
import cloudinary.uploader

# Initialize the Flask application
app = Flask(__name__)

# MongoDB configuration
app.config['MONGO_URI'] = "mongodb+srv://ali:12345@cluster0.awg30xs.mongodb.net/users?retryWrites=true&w=majority"

# JWT configuration
app.config['JWT_SECRET_KEY'] = 'afljkdkadfkljadaskflj'

# Cloudinary configuration
cloudinary.config(
  cloud_name="dfwahwlbc",
  api_key="874725767414532",
  api_secret="q7Xg6sDeCDB7S41C_2MGG7iIwFM"
)

# Initialize extensions
mongo = PyMongo(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)
CORS(app, supports_credentials=True, origins=['http://localhost:5173'])

# Test MongoDB connection
@app.route('/', methods=['GET'])
def test_db_connection():
    try:
        mongo.db.user.find_one()
        return jsonify({"message": "MongoDB connection successful"}), 200
    except Exception as e:
        return jsonify({"message": f"MongoDB connection failed: {str(e)}"}), 500

# Import and register blueprints
from app.api.Music.Musicroute import musicbp
from app.api.User.Userroute import userbp

app.register_blueprint(musicbp)
app.register_blueprint(userbp)

def create_app():
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)