from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import hashlib
import json
import jwt
import datetime
from functools import wraps
from flask_swagger_ui import get_swaggerui_blueprint
from dotenv import load_dotenv
from bson import ObjectId
from pymongo import MongoClient
import os

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# ------------------ MongoDB setup ------------------
client = MongoClient('mongodb://localhost:27017/')
db = client['soa_demo']

books_col = db['books']
members_col = db['members']
borrow_col = db['books_borrowed']

# ------------------ Helper functions ------------------

def generate_etag(data_dict):
    data_str = json.dumps(data_dict, sort_keys=True, default=str)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def success_response(data=None, message=None, status_code=200, etag=None):
    response = make_response(jsonify({
        "status": "success",
        "data": data,
        "message": message
    }), status_code)
    if etag:
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "private, max-age=120"
    return response

def error_response(message, status_code=400):
    return make_response(jsonify({
        "status": "error",
        "data": None,
        "message": message
    }), status_code)

def serialize_doc(doc):
    doc['_id'] = str(doc['_id'])
    return doc

# ------------------ AUTH ------------------

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            parts = request.headers['Authorization'].split()
            if len(parts) == 2 and parts[0] == 'Bearer':
                token = parts[1]
        if not token:
            return error_response("Token is missing", 401)
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user = data['user']
        except jwt.ExpiredSignatureError:
            return error_response("Token expired", 401)
        except jwt.InvalidTokenError:
            return error_response("Invalid token", 401)
        return f(current_user, *args, **kwargs)
    return decorated

@app.route('/api/v1/login', methods=['POST'])
def login():
    body = request.get_json()
    username = body.get('username')
    password = body.get('password')
    if username == 'admin' and password == '123456':
        token = jwt.encode({
            'user': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return success_response({"token": token}, "Login successful")
    return error_response("Invalid credentials", 401)

# ------------------ BOOKS ------------------

@app.route('/api/v1/books', methods=['GET'])
@token_required
def get_books(current_user):
    query = {}
    available = request.args.get('available')
    if available is not None:
        query['available'] = available.lower() == 'true'

    title = request.args.get('title')
    author = request.args.get('author')
    if title:
        query['title'] = {'$regex': title, '$options': 'i'}
    if author:
        query['author'] = {'$regex': author, '$options': 'i'}

    books = list(books_col.find(query).limit(20))
    books = [serialize_doc(b) for b in books]
    etag = generate_etag(books)
    return success_response({"books": books}, "Books fetched successfully", etag=etag)

@app.route('/api/v1/books', methods=['POST'])
@token_required
def create_book(current_user):
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return error_response("Missing title or author", 400)
    book = {
        "title": data['title'],
        "author": data['author'],
        "available": True
    }
    result = books_col.insert_one(book)
    book['_id'] = str(result.inserted_id)
    etag = generate_etag(book)
    return success_response(book, "Book created", 201, etag)

@app.route('/api/v1/books/<book_id>', methods=['GET'])
@token_required
def get_book(current_user, book_id):
    book = books_col.find_one({"_id": ObjectId(book_id)})
    if not book:
        return error_response("Book not found", 404)
    book = serialize_doc(book)
    etag = generate_etag(book)
    client_etag = request.headers.get('If-None-Match')
    if client_etag == etag:
        return '', 304
    return success_response(book, etag=etag)

@app.route('/api/v1/books/<book_id>', methods=['PUT'])
@token_required
def update_book(current_user, book_id):
    data = request.get_json()
    update_fields = {}
    for key in ['title', 'author', 'available']:
        if key in data:
            update_fields[key] = data[key]
    result = books_col.update_one({"_id": ObjectId(book_id)}, {"$set": update_fields})
    if result.matched_count == 0:
        return error_response("Book not found", 404)
    book = books_col.find_one({"_id": ObjectId(book_id)})
    book = serialize_doc(book)
    return success_response(book, "Book updated", etag=generate_etag(book))

@app.route('/api/v1/books/<book_id>', methods=['DELETE'])
@token_required
def delete_book(current_user, book_id):
    result = books_col.delete_one({"_id": ObjectId(book_id)})
    if result.deleted_count == 0:
        return error_response("Book not found", 404)
    return success_response(None, "Book deleted")

# ------------------ MEMBERS ------------------

@app.route('/api/v1/members', methods=['POST'])
@token_required
def create_member(current_user):
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        return error_response("Missing name or email", 400)
    existing = members_col.find_one({"email": data['email']})
    if existing:
        return error_response("Email already exists", 400)
    member = {
        "name": data['name'],
        "email": data['email'],
        "join_date": datetime.datetime.utcnow()
    }
    res = members_col.insert_one(member)
    member['_id'] = str(res.inserted_id)
    return success_response(member, "Member created", 201)

@app.route('/api/v1/members', methods=['GET'])
@token_required
def get_members(current_user):
    members = list(members_col.find().limit(20))
    members = [serialize_doc(m) for m in members]
    return success_response({"members": members}, "Members fetched successfully")

# ------------------ Swagger ------------------

SWAGGER_URL = '/docs'
API_URL = '/static/swagger.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={'app_name': "Book Management API"})
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

@app.route('/')
def home():
    return 'Swagger UI available at /docs'

if __name__ == '__main__':
    app.run(debug=True, port=5001)
