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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import requests
from threading import Thread

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "defaultsecret")
app.config['MONGO_URI'] = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
app.config['MONGO_DB_NAME'] = os.getenv("MONGO_DB_NAME", "library_db")

# Cấu hình Webhook URL (có thể lưu trong .env hoặc database)
app.config['WEBHOOK_URL'] = os.getenv("WEBHOOK_URL", None)

limiter = Limiter(
    key_func=get_remote_address
)
limiter.init_app(app)


# ------------------ MongoDB setup ------------------
client = MongoClient(app.config['MONGO_URI'])
db = client[app.config['MONGO_DB_NAME']]
books_col = db['books']


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


# ------------------ WEBHOOK FUNCTIONS ------------------

def send_webhook_notification(event_type, data):
    """
    Gửi thông báo webhook (chạy trong background thread)
    """
    def _send():
        webhook_url = app.config.get('WEBHOOK_URL')
        
        if not webhook_url:
            print("⚠️ WEBHOOK_URL chưa được cấu hình")
            return
        
        try:
            payload = {
                "event": event_type,
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "data": data
            }
            
            
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=5,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Library-Management-System/1.0"
                }
            )
            
         
            
        except requests.exceptions.Timeout:
            print(f"❌ Webhook timeout: {webhook_url}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to webhook: {webhook_url}")
        except Exception as e:
            print(f"❌ Failed to send webhook: {str(e)}")
    
    # Chạy trong background thread để không block API response
    thread = Thread(target=_send)
    thread.daemon = True
    thread.start()


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
@limiter.limit("20 per minute") 
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
@limiter.limit("10 per minute")
def create_book(current_user):
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return error_response("Missing title or author", 400)
    
    book = {
        "title": data['title'],
        "author": data['author'],
        "available": True,
        "created_at": datetime.datetime.utcnow(),
        "created_by": current_user
    }
    
    result = books_col.insert_one(book)
    book['_id'] = str(result.inserted_id)
    
    # 🔔 GỬI WEBHOOK NOTIFICATION KHI CÓ SÁCH MỚI ĐƯỢC TẠO
    webhook_data = {
        "book_id": book['_id'],
        "title": book['title'],
        "author": book['author'],
        "available": book['available'],
        "created_by": current_user,
        "created_at": book['created_at'].isoformat() + "Z",
        "message": f"📚 Sách mới '{book['title']}' của tác giả {book['author']} đã được thêm vào thư viện!"
    }
    
    send_webhook_notification("book.created", webhook_data)
    
    etag = generate_etag(book)
    return success_response(book, "Book created and webhook notification sent", 201, etag)

@app.route('/api/v1/books/<book_id>', methods=['GET'])
@token_required
@limiter.limit("10 per minute")
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
@limiter.limit("10 per minute")
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
@limiter.limit("10 per minute")
def delete_book(current_user, book_id):
    result = books_col.delete_one({"_id": ObjectId(book_id)})
    if result.deleted_count == 0:
        return error_response("Book not found", 404)
    return success_response(None, "Book deleted")


# ------------------ WEBHOOK CONFIG ENDPOINT ------------------

@app.route('/api/v1/webhook/config', methods=['GET'])
@token_required
def get_webhook_config(current_user):
    """Lấy thông tin cấu hình webhook hiện tại"""
    webhook_url = app.config.get('WEBHOOK_URL')
    return success_response({
        "webhook_url": webhook_url if webhook_url else None,
        "configured": webhook_url is not None
    }, "Webhook configuration retrieved")


@app.route('/api/v1/webhook/config', methods=['POST'])
@token_required
def set_webhook_config(current_user):
    """Cập nhật webhook URL (chỉ admin mới được phép)"""
    if current_user != 'admin':
        return error_response("Only admin can configure webhook", 403)
    
    data = request.get_json()
    webhook_url = data.get('webhook_url')
    
    if not webhook_url:
        return error_response("webhook_url is required", 400)
    
    # Validate URL format
    if not webhook_url.startswith(('http://', 'https://')):
        return error_response("Invalid webhook URL format", 400)
    
    app.config['WEBHOOK_URL'] = webhook_url
    
    return success_response({
        "webhook_url": webhook_url,
        "message": "Webhook URL configured successfully. You can test it now."
    }, "Webhook configured")


@app.route('/api/v1/webhook/test', methods=['POST'])
@token_required
def test_webhook(current_user):
    """Test gửi webhook với dữ liệu mẫu"""
    webhook_url = app.config.get('WEBHOOK_URL')
    
    if not webhook_url:
        return error_response("Webhook URL chưa được cấu hình. Vui lòng cấu hình tại POST /api/v1/webhook/config", 400)
    
    test_data = {
        "book_id": "test_" + datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S"),
        "title": "Test Book - Clean Code",
        "author": "Robert C. Martin",
        "available": True,
        "created_by": current_user,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "message": "🧪 Đây là TEST webhook notification từ hệ thống Library Management"
    }
    
    try:
        response = requests.post(
            webhook_url,
            json={
                "event": "book.created.test",
                "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
                "data": test_data
            },
            timeout=5,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Library-Management-System/1.0"
            }
        )
        
        return success_response({
            "webhook_url": webhook_url,
            "status_code": response.status_code,
            "response_preview": response.text[:500],
            "message": "Test webhook sent successfully"
        }, "Test completed")
        
    except Exception as e:
        return error_response(f"Failed to send test webhook: {str(e)}", 500)


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
    webhook_status = "✅ Configured" if app.config.get('WEBHOOK_URL') else "❌ Not configured"
    return f'''
    <h1>📚 Book Management API with Webhook Notifications</h1>
    <p><strong>Webhook Status:</strong> {webhook_status}</p>
    
    <h3>📖 Documentation:</h3>
    <ul>
        <li><a href="/docs">Swagger UI</a></li>
    </ul>
    
    <h3>🚀 Quick Start Guide:</h3>
    <ol>
        <li><strong>Setup ngrok:</strong>
            <pre>ngrok http http://127.0.0.1:5000</pre>
        </li>
        <li><strong>Login:</strong> POST /api/v1/login (admin/123456)</li>
        <li><strong>Configure Webhook:</strong> 
            <pre>POST /api/v1/webhook/config
{{ "webhook_url": "https://your-ngrok-url.ngrok-free.app/webhook" }}</pre>
        </li>
        <li><strong>Test Webhook:</strong> POST /api/v1/webhook/test</li>
        <li><strong>Create Book:</strong> POST /api/v1/books (webhook sẽ tự động gửi thông báo)</li>
    </ol>
    
    <h3>🔗 Webhook Endpoints:</h3>
    <ul>
        <li>GET /api/v1/webhook/config - Xem cấu hình webhook</li>
        <li>POST /api/v1/webhook/config - Cấu hình webhook URL</li>
        <li>POST /api/v1/webhook/test - Test gửi webhook</li>
    </ul>
    '''

if __name__ == '__main__':
    print("=" * 60)
    print("📚 LIBRARY MANAGEMENT API WITH WEBHOOK")
    print("=" * 60)
    print(f"🚀 Server running on: http://0.0.0.0:5001")
    print(f"📖 Swagger Docs: http://localhost:5001/docs")
    print(f"🔔 Webhook Status: {'Configured' if app.config.get('WEBHOOK_URL') else 'Not configured'}")
    if app.config.get('WEBHOOK_URL'):
        print(f"   URL: {app.config['WEBHOOK_URL']}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5001)