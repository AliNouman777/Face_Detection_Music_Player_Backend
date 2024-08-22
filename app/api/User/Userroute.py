import logging
from flask import Blueprint, request, jsonify, make_response
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta
from flask_cors import cross_origin
from bson import ObjectId
from datetime import datetime


from app import mongo, bcrypt
from app.models.usermodel import User

userbp = Blueprint("user", __name__)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Register User Route
@userbp.route("/user/register", methods=['POST'])
def regUser():
    try:
        username = request.json.get('username')
        password = request.json.get('password')
        email = request.json.get('email')

        logging.debug(f"Registering user: {username}, {email}")

        if not username or not password or not email:
            logging.error("Missing fields in registration request")
            return jsonify({"message": "Missing fields"}), 400

        user = User.find_by_email(email)
        if user:
            logging.error("User already exists")
            return jsonify({"message": "User already exists"}), 409

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        newuser = User(username, email, hashed_password)
        user_id = newuser.save()

        accesstoken = create_access_token(identity=str(user_id), expires_delta=timedelta(days=1))
        response = make_response(jsonify({"message": "User created successfully", "user_id": str(user_id)}), 201)

        logging.debug("User registered successfully")
        return response

    except Exception as e:
        logging.error(f"Error during user registration: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

# Login Route
@userbp.route("/user/login", methods=['POST'])
@cross_origin(supports_credentials=True)
def loginUser():
    try:
        email = request.json.get('email', None)
        password = request.json.get('password', None)

        if not email or not password:
            logging.error("Missing credentials in login request")
            return jsonify({"message": "Missing credentials"}), 400

        user = User.find_by_email(email)
        if user and bcrypt.check_password_hash(user['password'], password):
            accesstoken = create_access_token(identity=str(user['_id']), expires_delta=timedelta(days=1))
            return jsonify(access_token=accesstoken, message="Login successful"), 200
        else:
            logging.error("Invalid credentials")
            return jsonify({"message": "Invalid credentials"}), 401

    except Exception as e:
        logging.error(f"Error during user login: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

# Logout Route
@userbp.route("/user/logout", methods=['POST'])
@jwt_required()
def logoutUser():
    try:
        user_id = get_jwt_identity()
        if user_id:
            response = make_response(jsonify({"message": "Logout successful"}), 200)
            return response
        else:
            logging.error("Not logged in")
            return jsonify({"message": "Not logged in"}), 401
    except Exception as e:
        logging.error(f"Error during user logout: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

# Profile Route
@userbp.route("/user/profile", methods=['GET'])
@jwt_required()
def getUserProfile():
    try:
        user_id = get_jwt_identity()
        Userid = ObjectId(user_id)

        user = User.find_by_id(Userid)
        if user:
            return jsonify({
                "username": user['username'],
                "email": user['email'].strip(),
                "isAdmin": user.get('isAdmin', False)
            }), 200
        else:
            logging.error("User not found")
            return jsonify({"message": "User not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching user profile: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

# User Stats Route
@userbp.route("/user/stats", methods=["GET"])
@jwt_required()
def monthly_user_stats():
    try:
        now = datetime.utcnow()
        current_year = now.year
        monthly_stats = {month: 0 for month in range(1, 13)}

        users = mongo.db.user.find({
            "created_at": {
                "$gte": datetime(current_year, 1, 1),
                "$lt": datetime(current_year + 1, 1, 1)
            }
        })

        for user in users:
            month = user['created_at'].month
            monthly_stats[month] += 1

        monthly_stats_readable = {
            "January": monthly_stats[1],
            "February": monthly_stats[2],
            "March": monthly_stats[3],
            "April": monthly_stats[4],
            "May": monthly_stats[5],
            "June": monthly_stats[6],
            "July": monthly_stats[7],
            "August": monthly_stats[8],
            "September": monthly_stats[9],
            "October": monthly_stats[10],
            "November": monthly_stats[11],
            "December": monthly_stats[12],
        }

        return jsonify({
            "message": "Monthly user registration stats retrieved successfully",
            "year": current_year,
            "monthly_registrations": monthly_stats_readable
        }), 200

    except Exception as e:
        logging.error(f"Error fetching monthly user registration stats: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

# Fetch All Users Route
@userbp.route("/user/all", methods=["GET"])
@jwt_required()
def getAllUsers():
    try:
        users = mongo.db.user.find()
        users_list = []
        for user in users:
            user_data = {
                "id": str(user['_id']),
                "username": user['username'],
                "email": user['email'],
                "isAdmin": user.get('isAdmin', False),
                "created_at": user['created_at']
            }
            users_list.append(user_data)

        return jsonify({"users": users_list}), 200

    except Exception as e:
        logging.error(f"Error fetching all users: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

# Delete All Users Route
@userbp.route("/user/delete/<id>", methods=["DELETE"])
@jwt_required()
def deleteUser(id):
    try:
        user_id = get_jwt_identity()
        Userid = ObjectId(user_id)
        user = mongo.db.user.find_one({"_id": Userid})

        if not user or not user.get("isAdmin", False):
            return jsonify({"message": "Unauthorized"}), 403

        result = mongo.db.user.delete_one({"_id": ObjectId(id)})

        if result.deleted_count:
            return jsonify({"message": "User deleted successfully"}), 200
        else:
            return jsonify({"message": "User not found"}), 404

    except Exception as e:
        logging.error(f"Error deleting user: {str(e)}")
        return jsonify({"message": "Internal Server Error"}), 500

