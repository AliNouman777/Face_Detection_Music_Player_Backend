from datetime import datetime
from bson import ObjectId
from app import mongo

class User:
    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.password = password
        self.created_at = datetime.utcnow()

    def save(self):
        user_document = {
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "isAdmin": False,
            "created_at": self.created_at
        }
        result = mongo.db.user.insert_one(user_document)
        return str(result.inserted_id)

    @staticmethod
    def find_by_email(email):
        return mongo.db.user.find_one({"email": email})

    @staticmethod
    def find_by_id(user_id):
        return mongo.db.user.find_one({"_id": ObjectId(user_id)})
