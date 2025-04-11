import logging
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import cloudinary.uploader
from app import mongo
from datetime import datetime
from bson.objectid import ObjectId
from PIL import Image
from tensorflow.keras.models import load_model
from werkzeug.exceptions import BadRequest
from bson.errors import InvalidId
import io
import base64
import numpy as np
import os
from tenacity import retry, stop_after_attempt, wait_fixed
from functools import wraps
from config import Config

# Configure logging
logger = logging.getLogger(__name__)

# Load model once at startup
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'model.h5')
model = load_model(model_path)

musicbp = Blueprint('music', __name__)
emotion_labels = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = get_jwt_identity()
        try:
            user = mongo.db.user.find_one({"_id": ObjectId(user_id)})
            if not user or not user.get("isAdmin", False):
                logger.warning(f"Unauthorized admin access attempt by user: {user_id}")
                return jsonify({"message": "Unauthorized"}), 403
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Admin check failed: {str(e)}")
            return jsonify({"message": "Authorization check failed"}), 500
    return decorated

@musicbp.route('/music/upload', methods=['POST'])
@jwt_required()
@admin_required
def mupload():
    try:
        if 'file' not in request.files:
            raise BadRequest("No file part")
            
        file = request.files['file']
        if file.filename == '':
            raise BadRequest("No selected file")
            
        required_fields = ['musictype', 'singer', 'title', 'description']
        if any(field not in request.form for field in required_fields):
            raise BadRequest("Missing required fields")

        upload_result = cloudinary.uploader.upload(
            file,
            resource_type="auto",
            folder="music_uploads",
            allowed_formats=['mp3', 'wav', 'ogg']
        )
        
        music_data = {
            "user_id": get_jwt_identity(),
            "public_id": upload_result['public_id'],
            "music_link": upload_result['secure_url'],
            "type": request.form['musictype'],
            "singer": request.form['singer'],
            "title": request.form['title'],
            "description": request.form['description'],
            "uploaded_at": datetime.utcnow()
        }
        
        result = mongo.db.music.insert_one(music_data)
        logger.info(f"Music uploaded successfully: {result.inserted_id}")
        
        return jsonify({
            "message": "Music uploaded successfully",
            "music_id": str(result.inserted_id),
            "music_link": music_data['music_link']
        }), 201
        
    except cloudinary.exceptions.Error as e:
        logger.error(f"Cloudinary upload failed: {str(e)}")
        return jsonify({"message": "File upload failed"}), 500
    except Exception as e:
        logger.error(f"Music upload error: {str(e)}")
        return jsonify({"message": "Music upload failed"}), 500

@musicbp.route('/music/delete/<id>', methods=['DELETE'])
@jwt_required()
@admin_required
def delete(id):
    try:
        music_id = ObjectId(id)
        music = mongo.db.music.find_one({"_id": music_id})
        
        if not music:
            return jsonify({"message": "Music not found"}), 404
            
        cloudinary.uploader.destroy(music['public_id'])
        delete_result = mongo.db.music.delete_one({"_id": music_id})
        
        if delete_result.deleted_count == 0:
            return jsonify({"message": "Music not found"}), 404
            
        logger.info(f"Music deleted: {id}")
        return jsonify({"message": "Music deleted successfully"}), 200
        
    except InvalidId:
        logger.warning(f"Invalid music ID format: {id}")
        return jsonify({"message": "Invalid music ID format"}), 400
    except Exception as e:
        logger.error(f"Music deletion error: {str(e)}")
        return jsonify({"message": "Music deletion failed"}), 500

@musicbp.route('/music/all', methods=['GET'])
@jwt_required()
@admin_required
def allmusic():
    try:
        music = mongo.db.music.find().sort("uploaded_at", -1).limit(100)
        music_list = []
        
        for item in music:
            item['_id'] = str(item['_id'])
            item['user_id'] = str(item.get('user_id', ''))
            music_list.append(item)
            
        return jsonify(music_list), 200
        
    except Exception as e:
        logger.error(f"Music list retrieval failed: {str(e)}")
        return jsonify({"message": "Failed to retrieve music list"}), 500

@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def preprocessing_img(img_data):
    try:
        header, encoded = img_data.split(",", 1)
        image_bytes = base64.b64decode(encoded)
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert('L').resize((128, 128), Image.Resampling.LANCZOS)
        image_array = np.array(image) / 255.0
        return np.expand_dims(image_array, axis=(0, -1))
    except (ValueError, IOError) as e:
        logger.error(f"Image processing error: {str(e)}")
        raise BadRequest("Invalid image data")
    except Exception as e:
        logger.error(f"Unexpected image processing error: {str(e)}")
        raise

@musicbp.route('/music/getimg', methods=['POST'])
def search_music():
    try:
        data = request.get_json()
        if 'image' not in data:
            raise BadRequest("No image data provided")
            
        processed_img = preprocessing_img(data['image'])
        prediction = model.predict(processed_img)
        musictype = emotion_labels[np.argmax(prediction)]
        
        query = {"type": musictype}
        if 'singer' in data:
            query['singer'] = data['singer']
            
        music = mongo.db.music.find(query).limit(50)
        music_list = [{**item, '_id': str(item['_id'])} for item in music]
        
        if not music_list:
            return jsonify({"message": "No music found", "mood": musictype}), 404
            
        return jsonify({
            "mood": musictype,
            "results": music_list,
            "count": len(music_list)
        }), 200
        
    except BadRequest as e:
        logger.warning(f"Bad request: {str(e)}")
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        logger.error(f"Music search error: {str(e)}")
        return jsonify({"message": "Music search failed"}), 500

@musicbp.route('/music/stats', methods=['GET'])
@jwt_required()
def get_music_stats():
    try:
        # Ensure the user is an admin
        user_id = get_jwt_identity()
        Userid = ObjectId(user_id)
        user = mongo.db.user.find_one({"_id": Userid})
        if not user or not user.get("isAdmin", True):
            return jsonify({"message": "Unauthorized"}), 403

        # Aggregate to get the count of each music type
        pipeline = [
            {"$group": {"_id": "$type", "count": {"$sum": 1}}},
            {"$sort": {"_id": 1}}  # Sort by music type (optional)
        ]
        result = mongo.db.music.aggregate(pipeline)

        # Extract the types and their counts from the aggregation result
        music_stats = {doc['_id']: doc['count'] for doc in result}

        # Get the total number of songs
        total_songs = mongo.db.music.count_documents({})

        return jsonify({
            "total_songs": total_songs,
            "music_stats": music_stats
        }), 200

    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500
