from flask import Flask, request, jsonify, make_response, send_from_directory
from flask_cors import CORS
import hashlib
import json
import jwt
import datetime
from functools import wraps
from flask_swagger_ui import get_swaggerui_blueprint
from dotenv import load_dotenv
from mongoengine import Document, StringField, BooleanField, connect
import os

# ------------------ Setup ------------------
load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "defaultsecret")
app.config['MONGO_URI'] = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
app.config['MONGO_DB_NAME'] = os.getenv("MONGO_DB_NAME", "library_db")

# ------------------ MongoDB ORM setup ------------------


connect(
    db=app.config['MONGO_DB_NAME'],
    host=app.config['MONGO_URI']
)
print("Connected OK")
# ------------------ MongoEngine Model ------------------
class Book(Document):
    title = StringField(required=True)
    author = StringField(required=True)
    available = BooleanField(default=True)

    def to_dict(self):
        return {
            "_id": str(self.id),
            "title": self.title,
            "author": self.author,
            "available": self.available
        }

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

# ------------------ BOOKS API ------------------
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
        query['title__icontains'] = title
    if author:
        query['author__icontains'] = author

    books = Book.objects(**query)[:20]
    books_list = [b.to_dict() for b in books]
    etag = generate_etag(books_list)
    return success_response({"books": books_list}, "Books fetched successfully", etag=etag)

@app.route('/api/v1/books', methods=['POST'])
@token_required
def create_book(current_user):
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return error_response("Missing title or author", 400)
    book = Book(title=data['title'], author=data['author'], available=True)
    book.save()
    book_dict = book.to_dict()
    return success_response(book_dict, "Book created", 201, generate_etag(book_dict))

@app.route('/api/v1/books/<book_id>', methods=['GET'])
@token_required
def get_book(current_user, book_id):
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return error_response("Book not found", 404)
    book_dict = book.to_dict()
    etag = generate_etag(book_dict)
    client_etag = request.headers.get('If-None-Match')
    if client_etag == etag:
        return '', 304
    return success_response(book_dict, etag=etag)

@app.route('/api/v1/books/<book_id>', methods=['PUT'])
@token_required
def update_book(current_user, book_id):
    data = request.get_json()
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return error_response("Book not found", 404)
    for key in ['title', 'author', 'available']:
        if key in data:
            setattr(book, key, data[key])
    book.save()
    book_dict = book.to_dict()
    return success_response(book_dict, "Book updated", etag=generate_etag(book_dict))

@app.route('/api/v1/books/<book_id>', methods=['DELETE'])
@token_required
def delete_book(current_user, book_id):
    try:
        book = Book.objects.get(id=book_id)
    except Book.DoesNotExist:
        return error_response("Book not found", 404)
    book.delete()
    return success_response(None, "Book deleted")

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
