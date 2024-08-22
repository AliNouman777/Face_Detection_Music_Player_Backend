from flask import Blueprint, request, jsonify, Response
from flask_jwt_extended import jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
import cloudinary.uploader
from app import mongo
from datetime import datetime
from bson.objectid import ObjectId
from bson import json_util
from PIL import Image
from tensorflow.keras.models import load_model
from werkzeug.exceptions import BadRequest
import io
import base64
import numpy as np
import matplotlib.pyplot as plt
from bson.errors import InvalidId
import os


current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'model.h5')

# Now load the model
model = load_model(model_path)

musicbp = Blueprint('music', __name__)

@musicbp.route('/music/upload', methods=['POST'])
@jwt_required()
def mupload():
    user_id = get_jwt_identity()
    Userid = ObjectId(user_id)
    user = mongo.db.user.find_one({"_id": Userid})
    
    if not user or not user.get("isAdmin", True):
        return jsonify({"message": "Unauthorized"}), 403
    
    if 'file' not in request.files: 
        return jsonify({"message": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400 
    
    musictype = request.form.get('musictype', '') 
    singer = request.form.get('singer', '')
    title = request.form.get('title', '')
    description = request.form.get('description', '')

    if not musictype or not singer or not title or not description:
        return jsonify({"message": "Missing fields"}), 400 

    if file:
        upload_result = cloudinary.uploader.upload(file, resource_type="auto")
        musiclink = upload_result.get('url')
        public_id = upload_result.get('public_id')
        mongo.db.music.insert_one({
            "user_id": user_id,
            "public_id": public_id,
            "music_link": musiclink,
            "type": musictype,
            "singer": singer,
            "title": title,
            "description": description,
            "uploaded_at": datetime.utcnow()
        })

        return jsonify({"message": "Music uploaded successfully", "music_link": musiclink}), 200
    

@musicbp.route('/music/delete/<id>', methods=['DELETE'])
@jwt_required()
def delete(id):
    user_id = get_jwt_identity()
    Userid = ObjectId(user_id)
    user = mongo.db.user.find_one({"_id": Userid})

    if not user or not user.get("isAdmin", True):
        return jsonify({"message": "Unauthorized"}), 403

    music_entity = mongo.db.music.find_one({"_id": ObjectId(id)})

    if not music_entity:
        return jsonify({"message": "Music not found"}), 404

    public_id = music_entity.get('public_id')
    cloudinary.uploader.destroy(public_id)  # Deleting the file from Cloudinary
    
    result = mongo.db.music.delete_one({"_id": ObjectId(id)})  # Deleting the music entry

    if result.deleted_count:
        return jsonify({"message": "Music deleted successfully"}), 200
    else:
        return jsonify({"message": "Music not found"}), 404


@musicbp.route('/music/all', methods=['GET'])
@jwt_required()
def allmusic():
    user_id = get_jwt_identity()
    Userid = ObjectId(user_id)
    user = mongo.db.user.find_one({"_id": Userid})
    if not user or not user.get("isAdmin", True):
        return jsonify({"message": "Unauthorized"}), 403  
    
    music = mongo.db.music.find()
    music_list = [{**music, '_id': str(music['_id']), 'user_id': str(music['user_id'])} for music in music]
    
    return jsonify(music_list), 200


@musicbp.route("/music/update/<id>", methods=["PUT"])
@jwt_required()
def update(id): 
    try:

        # Validate the ObjectId
        try:
            music_id = ObjectId(id)
        except InvalidId:
            return jsonify({"message": "Invalid music ID provided."}), 400

        user_id = get_jwt_identity()
        Userid = ObjectId(user_id)
        user = mongo.db.user.find_one({"_id": Userid})
        
        if not user or not user.get("isAdmin", False):
            return jsonify({"message": "Unauthorized"}), 403

        music = mongo.db.music.find_one({"_id": music_id})
        if not music:
            return jsonify({"message": "Music not found"}), 404

        data = request.get_json()
        
        # Prepare the fields for update
        update_fields = {}
        if 'musictype' in data:
            update_fields['type'] = data['musictype']
        if 'singer' in data:
            update_fields['singer'] = data['singer']
        if 'title' in data:
            update_fields['title'] = data['title']
        if 'description' in data:
            update_fields['description'] = data['description']

        if not update_fields:
            return jsonify({"message": "No changes provided."}), 400

        update_fields['updated_at'] = datetime.utcnow()

        updated_result = mongo.db.music.update_one(
            {"_id": music_id},
            {"$set": update_fields}
        )

        if updated_result.modified_count:
            updated_music = mongo.db.music.find_one({"_id": music_id})
            # Convert ObjectId fields to strings
            updated_music['_id'] = str(updated_music['_id'])
            updated_music['user_id'] = str(updated_music['user_id'])
            return jsonify({
                "message": "Music updated successfully",
                "music": updated_music  # Return the music document directly
            }), 200
        else:
            return jsonify({"message": "No changes made or music not found"}), 304

    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500


@musicbp.route('/music/types', methods=['GET'])
def get_music_types():
    pipeline = [
        {"$group": {"_id": "$type"}},
        {"$sort": {"_id": 1}} 
    ]
    result = mongo.db.music.aggregate(pipeline)
    
    # Extracting the types from the aggregation result
    types = [doc['_id'] for doc in result if doc['_id'] is not None]

    return jsonify({"music_types": types}), 200


@musicbp.route('/music/singers', methods=['GET'])
def get_music_singers():
    pipeline = [
        {"$group": {"_id": "$singer"}},
        {"$sort": {"_id": 1}} 
    ]
    result = mongo.db.music.aggregate(pipeline)

    singers = [doc['_id'] for doc in result if doc['_id'] is not None]

    return jsonify({"music_singers": singers}), 200


def preprocessing_img(img, size=(128,128)):
    try:
        image = Image.open(io.BytesIO(base64.b64decode(img.split(",")[1])))
        image = image.convert('L')
        image = image.resize(size, Image.Resampling.LANCZOS)
        image_array = np.array(image)
        image_array = image_array / 255.0
        image_array = np.expand_dims(image_array, axis=0)
        return image_array
    except Exception as e:
        raise BadRequest(f"Image preprocessing failed: {e}")

@musicbp.route('/music/getimg', methods=['POST'])
def search_music():
    emotion_labels = ['angry', 'disgust', 'fear', 'happy', 'neutral', 'sad', 'surprise']
    try:
        data = request.get_json()
        if 'image' not in data:
            raise BadRequest("No image data provided.")

        singer = data.get('singer')

        processimg = preprocessing_img(data['image'])
        prediction = model.predict(processimg)
        musictype_index = np.argmax(prediction, axis=1)[0]
        musictype = emotion_labels[musictype_index]
        query = {}
        if singer:
            query['singer'] = singer
        if musictype:
            query['type'] = musictype

        music_entries = mongo.db.music.find(query)
        music_list = [{**music, '_id': str(music['_id'])} for music in music_entries]
        if not music_list:
            return jsonify({"data": "No music found.", "mood" : musictype}), 404
        return jsonify({"data": music_list}), 200
    except BadRequest as e:
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500


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
