import connexion
from flask import jsonify, make_response, request
from typing import Dict, Tuple, Union
from pymongo import MongoClient
from bson import ObjectId
import json, hashlib, os, jwt, datetime
from dotenv import load_dotenv
from functools import wraps

from openapi_server.models.api_v1_books_get200_response import ApiV1BooksGet200Response
from openapi_server.models.book import Book
from openapi_server.models.new_book import NewBook
from openapi_server.models.update_book import UpdateBook

# Load env
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "defaultsecret")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "library_db")
# Kết nối MongoDB
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
books_col = db["books"]

# --------------------- Helper ---------------------

def generate_etag(data):
    """Tạo ETag từ dữ liệu JSON"""
    return hashlib.md5(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()

def token_required(f):
    """Kiểm tra JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            parts = request.headers["Authorization"].split()
            if len(parts) == 2 and parts[0] == "Bearer":
                token = parts[1]
        if not token:
            return jsonify({"status": "error", "message": "Token missing"}), 401
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"status": "error", "message": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"status": "error", "message": "Invalid token"}), 401
        return f(*args, **kwargs)
    return decorated

# --------------------- API HANDLERS ---------------------

@token_required
def api_v1_books_get(available=None, title=None, author=None, cursor=None, limit=None):
    """Lấy danh sách sách (GET /api/v1/books)"""
    query = {}
    if available is not None:
        query["available"] = bool(available)
    if title:
        query["title"] = {"$regex": title, "$options": "i"}
    if author:
        query["author"] = {"$regex": author, "$options": "i"}

    limit = int(limit) if limit else 10
    books_cursor = books_col.find(query).limit(limit)

    books = []
    for b in books_cursor:
        b["_id"] = str(b["_id"])
        books.append(b)

    data = {"books": books}
    etag = generate_etag(data)
    resp = make_response(jsonify({"status": "success", "data": data}), 200)
    resp.headers["ETag"] = etag
    return resp


@token_required
def api_v1_books_post(body):
    """Thêm sách mới (POST /api/v1/books)"""
    if connexion.request.is_json:
        new_book = NewBook.from_dict(connexion.request.get_json())
    else:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    book_data = {
        "title": new_book.title,
        "author": new_book.author,
        "available": True,
    }

    result = books_col.insert_one(book_data)
    book_data["_id"] = str(result.inserted_id)
    return jsonify({"status": "success", "data": {"book": book_data}}), 201


@token_required
def api_v1_books_book_id_get(book_id):
    """Lấy thông tin 1 sách (GET /api/v1/books/{book_id})"""
    try:
        book = books_col.find_one({"_id": ObjectId(book_id)})
    except:
        return jsonify({"status": "error", "message": "Invalid book ID"}), 400
    if not book:
        return jsonify({"status": "error", "message": "Book not found"}), 404

    book["_id"] = str(book["_id"])
    etag = generate_etag(book)
    resp = make_response(jsonify({"status": "success", "data": {"book": book}}), 200)
    resp.headers["ETag"] = etag
    return resp


@token_required
def api_v1_books_book_id_put(book_id, body):
    """Cập nhật thông tin hoặc xử lý mượn/trả sách (PUT /api/v1/books/{book_id})"""
    if connexion.request.is_json:
        update_book = UpdateBook.from_dict(connexion.request.get_json())
    else:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    try:
        book = books_col.find_one({"_id": ObjectId(book_id)})
    except:
        return jsonify({"status": "error", "message": "Invalid book ID"}), 400

    if not book:
        return jsonify({"status": "error", "message": "Book not found"}), 404

    updates = {}
    if update_book.title is not None:
        updates["title"] = update_book.title
    if update_book.author is not None:
        updates["author"] = update_book.author
    if update_book.available is not None:
        updates["available"] = update_book.available
    if update_book.borrowed_by is not None:
        updates["borrowed_by"] = update_book.borrowed_by

    books_col.update_one({"_id": ObjectId(book_id)}, {"$set": updates})
    book = books_col.find_one({"_id": ObjectId(book_id)})
    book["_id"] = str(book["_id"])
    return jsonify({"status": "success", "data": {"book": book}}), 200


@token_required
def api_v1_books_book_id_delete(book_id):
    """Xóa sách (DELETE /api/v1/books/{book_id})"""
    from bson.errors import InvalidId

    try:
        object_id = ObjectId(book_id)
    except InvalidId:
        return jsonify({"status": "error", "message": "Invalid book ID"}), 400

    result = books_col.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        return jsonify({"status": "error", "message": "Book not found"}), 404

    return jsonify({"status": "success", "message": "Book deleted successfully"}), 200
