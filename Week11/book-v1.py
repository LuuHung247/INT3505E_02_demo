from flask import Flask, request, jsonify, make_response, send_from_directory, url_for
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
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "defaultsecret")
app.config['MONGO_URI'] = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
app.config['MONGO_DB_NAME'] = os.getenv("MONGO_DB_NAME", "library_db")

limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

# MongoDB setup
client = MongoClient(app.config['MONGO_URI'])
db = client[app.config['MONGO_DB_NAME']]
books_col = db['books']
events_col = db['events']
webhooks_col = db['webhooks']

# Event store (in-memory for demo, should use Redis/DB in production)
event_subscribers = defaultdict(list)

# ------------------ Helper functions ------------------

def generate_etag(data_dict):
    data_str = json.dumps(data_dict, sort_keys=True, default=str)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def success_response(data=None, message=None, status_code=200, etag=None, links=None):
    response_body = {
        "status": "success",
        "data": data,
        "message": message
    }
    if links:  # HATEOAS support
        response_body["_links"] = links
    
    response = make_response(jsonify(response_body), status_code)
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

# ------------------ HATEOAS Links Builder ------------------

def build_book_links(book_id, include_collection=True):
    """Build HATEOAS links for a book resource"""
    links = {
        "self": {"href": url_for('get_book', book_id=book_id, _external=True)},
        "update": {"href": url_for('update_book', book_id=book_id, _external=True), "method": "PUT"},
        "delete": {"href": url_for('delete_book', book_id=book_id, _external=True), "method": "DELETE"},
        "borrow": {"href": url_for('borrow_book', book_id=book_id, _external=True), "method": "POST"},
        "return": {"href": url_for('return_book', book_id=book_id, _external=True), "method": "POST"}
    }
    if include_collection:
        links["collection"] = {"href": url_for('get_books', _external=True)}
    return links

def build_collection_links(page=1, per_page=20, total=0):
    """Build pagination links for collection"""
    links = {
        "self": {"href": url_for('get_books', page=page, per_page=per_page, _external=True)},
    }
    if page > 1:
        links["prev"] = {"href": url_for('get_books', page=page-1, per_page=per_page, _external=True)}
    if page * per_page < total:
        links["next"] = {"href": url_for('get_books', page=page+1, per_page=per_page, _external=True)}
    links["first"] = {"href": url_for('get_books', page=1, per_page=per_page, _external=True)}
    return links

# ------------------ Event-Driven Architecture ------------------

def publish_event(event_type, data):
    """Publish event to event store and notify subscribers"""
    event = {
        "event_type": event_type,
        "data": data,
        "timestamp": datetime.datetime.utcnow(),
        "event_id": str(ObjectId())
    }
    # Store event in database
    events_col.insert_one(event)
    
    # Notify webhooks asynchronously
    Thread(target=notify_webhooks, args=(event_type, event)).start()
    
    return event

def notify_webhooks(event_type, event):
    """Send webhook notifications to registered endpoints"""
    webhooks = list(webhooks_col.find({"event_type": event_type, "active": True}))
    for webhook in webhooks:
        try:
            requests.post(
                webhook['url'],
                json=event,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
        except Exception as e:
            print(f"Webhook notification failed: {e}")

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

# ------------------ BOOKS CRUD with HATEOAS ------------------

@app.route('/api/v1/books', methods=['GET'])
@token_required
@limiter.limit("20 per minute") 
def get_books(current_user):
    """
    Query Pattern: Support filtering, sorting, pagination
    HATEOAS: Include navigation links
    """
    # Pagination
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))
    skip = (page - 1) * per_page
    
    # Query filters
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

    # Sorting
    sort_by = request.args.get('sort_by', 'title')
    sort_order = -1 if request.args.get('sort_order') == 'desc' else 1
    
    # Execute query
    total = books_col.count_documents(query)
    books = list(books_col.find(query).sort(sort_by, sort_order).skip(skip).limit(per_page))
    books = [serialize_doc(b) for b in books]
    
    # Add HATEOAS links to each book
    for book in books:
        book['_links'] = build_book_links(book['_id'], include_collection=False)
    
    etag = generate_etag(books)
    links = build_collection_links(page, per_page, total)
    
    return success_response({
        "books": books,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page
        }
    }, "Books fetched successfully", etag=etag, links=links)

@app.route('/api/v1/books', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
def create_book(current_user):
    """CRUD Create + Event-Driven: Publish book.created event"""
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return error_response("Missing title or author", 400)
    
    book = {
        "title": data['title'],
        "author": data['author'],
        "isbn": data.get('isbn'),
        "published_year": data.get('published_year'),
        "available": True,
        "created_at": datetime.datetime.utcnow(),
        "updated_at": datetime.datetime.utcnow()
    }
    result = books_col.insert_one(book)
    book['_id'] = str(result.inserted_id)
    
    # Publish event
    publish_event("book.created", serialize_doc(book))
    
    etag = generate_etag(book)
    links = build_book_links(book['_id'])
    
    return success_response(book, "Book created", 201, etag, links)

@app.route('/api/v1/books/<book_id>', methods=['GET'])
@token_required
@limiter.limit("10 per minute")
def get_book(current_user, book_id):
    """CRUD Read + HATEOAS"""
    try:
        book = books_col.find_one({"_id": ObjectId(book_id)})
    except:
        return error_response("Invalid book ID", 400)
    
    if not book:
        return error_response("Book not found", 404)
    
    book = serialize_doc(book)
    etag = generate_etag(book)
    
    # ETag validation
    client_etag = request.headers.get('If-None-Match')
    if client_etag == etag:
        return '', 304
    
    links = build_book_links(book_id)
    return success_response(book, etag=etag, links=links)

@app.route('/api/v1/books/<book_id>', methods=['PUT'])
@token_required
@limiter.limit("10 per minute")
def update_book(current_user, book_id):
    """CRUD Update + Event-Driven"""
    data = request.get_json()
    update_fields = {}
    for key in ['title', 'author', 'isbn', 'published_year', 'available']:
        if key in data:
            update_fields[key] = data[key]
    
    update_fields['updated_at'] = datetime.datetime.utcnow()
    
    try:
        result = books_col.update_one({"_id": ObjectId(book_id)}, {"$set": update_fields})
    except:
        return error_response("Invalid book ID", 400)
    
    if result.matched_count == 0:
        return error_response("Book not found", 404)
    
    book = books_col.find_one({"_id": ObjectId(book_id)})
    book = serialize_doc(book)
    
    # Publish event
    publish_event("book.updated", book)
    
    links = build_book_links(book_id)
    return success_response(book, "Book updated", etag=generate_etag(book), links=links)

@app.route('/api/v1/books/<book_id>', methods=['DELETE'])
@token_required
@limiter.limit("10 per minute")
def delete_book(current_user, book_id):
    """CRUD Delete + Event-Driven"""
    try:
        result = books_col.delete_one({"_id": ObjectId(book_id)})
    except:
        return error_response("Invalid book ID", 400)
    
    if result.deleted_count == 0:
        return error_response("Book not found", 404)
    
    # Publish event
    publish_event("book.deleted", {"book_id": book_id, "deleted_by": current_user})
    
    return success_response(None, "Book deleted")

# ------------------ Business Logic Endpoints ------------------

@app.route('/api/v1/books/<book_id>/borrow', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
def borrow_book(current_user, book_id):
    """Business action with event publishing"""
    try:
        book = books_col.find_one({"_id": ObjectId(book_id)})
    except:
        return error_response("Invalid book ID", 400)
    
    if not book:
        return error_response("Book not found", 404)
    
    if not book.get('available', False):
        return error_response("Book is not available", 400)
    
    # Update book status
    books_col.update_one(
        {"_id": ObjectId(book_id)},
        {"$set": {"available": False, "borrowed_by": current_user, "borrowed_at": datetime.datetime.utcnow()}}
    )
    
    # Publish event
    publish_event("book.borrowed", {
        "book_id": book_id,
        "user": current_user,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    
    book = books_col.find_one({"_id": ObjectId(book_id)})
    book = serialize_doc(book)
    links = build_book_links(book_id)
    
    return success_response(book, "Book borrowed successfully", links=links)

@app.route('/api/v1/books/<book_id>/return', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
def return_book(current_user, book_id):
    """Business action with event publishing"""
    try:
        book = books_col.find_one({"_id": ObjectId(book_id)})
    except:
        return error_response("Invalid book ID", 400)
    
    if not book:
        return error_response("Book not found", 404)
    
    if book.get('available', True):
        return error_response("Book was not borrowed", 400)
    
    # Update book status
    books_col.update_one(
        {"_id": ObjectId(book_id)},
        {"$set": {"available": True}, "$unset": {"borrowed_by": "", "borrowed_at": ""}}
    )
    
    # Publish event
    publish_event("book.returned", {
        "book_id": book_id,
        "user": current_user,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    
    book = books_col.find_one({"_id": ObjectId(book_id)})
    book = serialize_doc(book)
    links = build_book_links(book_id)
    
    return success_response(book, "Book returned successfully", links=links)

# ------------------ Advanced Query Endpoints ------------------

@app.route('/api/v1/books/search', methods=['GET'])
@token_required
@limiter.limit("20 per minute")
def search_books(current_user):
    """Advanced search with multiple criteria"""
    q = request.args.get('q', '')
    min_year = request.args.get('min_year')
    max_year = request.args.get('max_year')
    
    query = {}
    if q:
        query['$or'] = [
            {'title': {'$regex': q, '$options': 'i'}},
            {'author': {'$regex': q, '$options': 'i'}},
            {'isbn': {'$regex': q, '$options': 'i'}}
        ]
    
    if min_year:
        query['published_year'] = {'$gte': int(min_year)}
    if max_year:
        query.setdefault('published_year', {})
        query['published_year']['$lte'] = int(max_year)
    
    books = list(books_col.find(query).limit(50))
    books = [serialize_doc(b) for b in books]
    
    for book in books:
        book['_links'] = build_book_links(book['_id'], include_collection=False)
    
    return success_response({"books": books, "count": len(books)}, "Search completed")

@app.route('/api/v1/books/stats', methods=['GET'])
@token_required
@limiter.limit("10 per minute")
def get_books_stats(current_user):
    """Aggregation query for statistics"""
    total = books_col.count_documents({})
    available = books_col.count_documents({"available": True})
    borrowed = total - available
    
    # Author statistics
    pipeline = [
        {"$group": {"_id": "$author", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 10}
    ]
    top_authors = list(books_col.aggregate(pipeline))
    
    stats = {
        "total_books": total,
        "available_books": available,
        "borrowed_books": borrowed,
        "top_authors": top_authors
    }
    
    return success_response(stats, "Statistics retrieved")

# ------------------ Webhook Management ------------------

@app.route('/api/v1/webhooks', methods=['POST'])
@token_required
@limiter.limit("5 per minute")
def register_webhook(current_user):
    """Register a webhook for event notifications"""
    data = request.get_json()
    if not data or not data.get('url') or not data.get('event_type'):
        return error_response("Missing url or event_type", 400)
    
    webhook = {
        "url": data['url'],
        "event_type": data['event_type'],
        "user": current_user,
        "active": True,
        "created_at": datetime.datetime.utcnow()
    }
    result = webhooks_col.insert_one(webhook)
    webhook['_id'] = str(result.inserted_id)
    
    return success_response(webhook, "Webhook registered", 201)

@app.route('/api/v1/webhooks', methods=['GET'])
@token_required
def list_webhooks(current_user):
    """List all webhooks for current user"""
    webhooks = list(webhooks_col.find({"user": current_user}))
    webhooks = [serialize_doc(w) for w in webhooks]
    return success_response({"webhooks": webhooks})

@app.route('/api/v1/webhooks/<webhook_id>', methods=['DELETE'])
@token_required
def delete_webhook(current_user, webhook_id):
    """Delete a webhook"""
    try:
        result = webhooks_col.delete_one({"_id": ObjectId(webhook_id), "user": current_user})
    except:
        return error_response("Invalid webhook ID", 400)
    
    if result.deleted_count == 0:
        return error_response("Webhook not found", 404)
    
    return success_response(None, "Webhook deleted")

# ------------------ Event Stream (Server-Sent Events) ------------------

@app.route('/api/v1/events/stream', methods=['GET'])
@token_required
def event_stream(current_user):
    """Server-Sent Events endpoint for real-time updates"""
    def generate():
        last_id = request.args.get('last_event_id')
        query = {}
        if last_id:
            query['event_id'] = {'$gt': last_id}
        
        while True:
            events = list(events_col.find(query).sort('timestamp', -1).limit(10))
            for event in events:
                yield f"data: {json.dumps(serialize_doc(event))}\n\n"
            import time
            time.sleep(5)
    
    return app.response_class(generate(), mimetype='text/event-stream')

@app.route('/api/v1/events', methods=['GET'])
@token_required
def get_events(current_user):
    """Get event history"""
    event_type = request.args.get('event_type')
    limit = int(request.args.get('limit', 50))
    
    query = {}
    if event_type:
        query['event_type'] = event_type
    
    events = list(events_col.find(query).sort('timestamp', -1).limit(limit))
    events = [serialize_doc(e) for e in events]
    
    return success_response({"events": events, "count": len(events)})

# ------------------ API Documentation ------------------

@app.route('/api/v1', methods=['GET'])
def api_root():
    """HATEOAS: API root with all available endpoints"""
    links = {
        "self": {"href": url_for('api_root', _external=True)},
        "login": {"href": url_for('login', _external=True), "method": "POST"},
        "books": {"href": url_for('get_books', _external=True)},
        "search": {"href": url_for('search_books', _external=True)},
        "stats": {"href": url_for('get_books_stats', _external=True)},
        "webhooks": {"href": url_for('list_webhooks', _external=True)},
        "events": {"href": url_for('get_events', _external=True)},
        "documentation": {"href": "/docs"}
    }
    return success_response(None, "API v1", links=links)

# ------------------ Swagger ------------------

SWAGGER_URL = '/docs'
API_URL = '/static/swagger-v2.yaml'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={'app_name': "Book Management API"})
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)

@app.route('/')
def home():
    return jsonify({
        "message": "Book Management API",
        "documentation": "/docs",
        "api_root": "/api/v1"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5001)