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

# OpenTelemetry imports - OTLP version
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

load_dotenv()

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "defaultsecret")
app.config['MONGO_URI'] = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
app.config['MONGO_DB_NAME'] = os.getenv("MONGO_DB_NAME", "library_db")

limiter = Limiter(key_func=get_remote_address)
limiter.init_app(app)

# ------------------ OpenTelemetry Setup with OTLP ------------------

def setup_tracing():
    """Initialize OpenTelemetry tracing with OTLP exporter"""
    
    try:
        # Get OTLP configuration
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        
        print(f"🔧 Configuring OTLP exporter:")
        print(f"   - Endpoint: {otlp_endpoint}")
        
        # Create resource with service information
        resource = Resource.create({
            "service.name": "book-api",
            "service.version": "1.0.0",
            "deployment.environment": os.getenv("ENVIRONMENT", "development")
        })
        
        # Set up tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)
        
        # Configure OTLP exporter (gRPC)
        otlp_exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            insecure=True  # Use insecure=False with TLS in production
        )
        
        # Use BatchSpanProcessor for better performance
        span_processor = BatchSpanProcessor(
            otlp_exporter,
            max_queue_size=2048,
            schedule_delay_millis=5000,  # Export every 5 seconds
            max_export_batch_size=512,
            export_timeout_millis=30000
        )
        
        tracer_provider.add_span_processor(span_processor)
        
        # Instrument Flask
        FlaskInstrumentor().instrument_app(app)
        print("   ✓ Flask instrumented")
        
        # Instrument PyMongo
        PymongoInstrumentor().instrument()
        print("   ✓ PyMongo instrumented")
        
        # Instrument requests library
        RequestsInstrumentor().instrument()
        print("   ✓ Requests instrumented")
        
        print("✅ OpenTelemetry tracing initialized with OTLP")
        print(f"📊 Sending traces to: {otlp_endpoint}")
        print(f"🔍 View traces at: http://localhost:16686 (Jaeger UI)")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize OpenTelemetry tracing: {e}")
        import traceback
        traceback.print_exc()
        return False

# Initialize tracing
tracing_enabled = setup_tracing()

# Get tracer for manual instrumentation
if tracing_enabled:
    tracer = trace.get_tracer(__name__)
else:
    # Fallback to no-op tracer if setup failed
    from opentelemetry.trace import NoOpTracer
    tracer = NoOpTracer()

# ------------------ MongoDB setup ------------------
client = MongoClient(app.config['MONGO_URI'])
db = client[app.config['MONGO_DB_NAME']]
books_col = db['books']

# ------------------ Helper functions ------------------

def generate_etag(data_dict):
    with tracer.start_as_current_span("generate_etag"):
        data_str = json.dumps(data_dict, sort_keys=True, default=str)
        etag = hashlib.md5(data_str.encode('utf-8')).hexdigest()
        # Add custom span attributes
        span = trace.get_current_span()
        span.set_attribute("etag.length", len(etag))
        return etag

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
    # Add error info to current span
    span = trace.get_current_span()
    span.set_attribute("error", True)
    span.set_attribute("error.message", message)
    span.set_attribute("http.status_code", status_code)
    
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
        with tracer.start_as_current_span("verify_token") as span:
            token = None
            if 'Authorization' in request.headers:
                parts = request.headers['Authorization'].split()
                if len(parts) == 2 and parts[0] == 'Bearer':
                    token = parts[1]
            
            if not token:
                span.set_attribute("auth.status", "missing_token")
                return error_response("Token is missing", 401)
            
            try:
                data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
                current_user = data['user']
                span.set_attribute("auth.status", "valid")
                span.set_attribute("auth.user", current_user)
            except jwt.ExpiredSignatureError:
                span.set_attribute("auth.status", "expired")
                return error_response("Token expired", 401)
            except jwt.InvalidTokenError:
                span.set_attribute("auth.status", "invalid")
                return error_response("Invalid token", 401)
            
            return f(current_user, *args, **kwargs)
    return decorated

@app.route('/api/v1/login', methods=['POST'])
def login():
    with tracer.start_as_current_span("authenticate_user") as span:
        body = request.get_json()
        username = body.get('username')
        password = body.get('password')
        
        span.set_attribute("auth.username", username)
        
        if username == 'admin' and password == '123456':
            token = jwt.encode({
                'user': username,
                'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
            }, app.config['SECRET_KEY'], algorithm="HS256")
            
            span.set_attribute("auth.success", True)
            return success_response({"token": token}, "Login successful")
        
        span.set_attribute("auth.success", False)
        return error_response("Invalid credentials", 401)

# ------------------ BOOKS ------------------

@app.route('/api/v1/books', methods=['GET'])
@token_required
@limiter.limit("20 per minute") 
def get_books(current_user):
    with tracer.start_as_current_span("build_query") as span:
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
        
        span.set_attribute("query.filters", str(query))
    
    with tracer.start_as_current_span("fetch_books_from_db") as span:
        books = list(books_col.find(query).limit(20))
        span.set_attribute("books.count", len(books))
    
    with tracer.start_as_current_span("serialize_books"):
        books = [serialize_doc(b) for b in books]
    
    etag = generate_etag(books)
    return success_response({"books": books}, "Books fetched successfully", etag=etag)

@app.route('/api/v1/books', methods=['POST'])
@token_required
@limiter.limit("10 per minute")
def create_book(current_user):
    with tracer.start_as_current_span("validate_book_data") as span:
        data = request.get_json()
        if not data or not data.get('title') or not data.get('author'):
            span.set_attribute("validation.failed", True)
            return error_response("Missing title or author", 400)
        
        span.set_attribute("book.title", data['title'])
        span.set_attribute("book.author", data['author'])
    
    with tracer.start_as_current_span("insert_book_to_db") as span:
        book = {
            "title": data['title'],
            "author": data['author'],
            "available": True
        }
        result = books_col.insert_one(book)
        book['_id'] = str(result.inserted_id)
        span.set_attribute("book.id", book['_id'])
    
    etag = generate_etag(book)
    return success_response(book, "Book created", 201, etag)

@app.route('/api/v1/books/<book_id>', methods=['GET'])
@token_required
@limiter.limit("10 per minute")
def get_book(current_user, book_id):
    with tracer.start_as_current_span("fetch_book_by_id") as span:
        span.set_attribute("book.id", book_id)
        
        book = books_col.find_one({"_id": ObjectId(book_id)})
        if not book:
            span.set_attribute("book.found", False)
            return error_response("Book not found", 404)
        
        span.set_attribute("book.found", True)
        book = serialize_doc(book)
    
    etag = generate_etag(book)
    client_etag = request.headers.get('If-None-Match')
    
    if client_etag == etag:
        span = trace.get_current_span()
        span.set_attribute("cache.hit", True)
        return '', 304
    
    return success_response(book, etag=etag)

@app.route('/api/v1/books/<book_id>', methods=['PUT'])
@token_required
@limiter.limit("10 per minute")
def update_book(current_user, book_id):
    with tracer.start_as_current_span("prepare_update") as span:
        data = request.get_json()
        update_fields = {}
        for key in ['title', 'author', 'available']:
            if key in data:
                update_fields[key] = data[key]
        
        span.set_attribute("book.id", book_id)
        span.set_attribute("update.fields", str(update_fields))
    
    with tracer.start_as_current_span("update_book_in_db") as span:
        result = books_col.update_one({"_id": ObjectId(book_id)}, {"$set": update_fields})
        
        if result.matched_count == 0:
            span.set_attribute("book.found", False)
            return error_response("Book not found", 404)
        
        span.set_attribute("book.found", True)
        span.set_attribute("book.modified", result.modified_count > 0)
    
    book = books_col.find_one({"_id": ObjectId(book_id)})
    book = serialize_doc(book)
    return success_response(book, "Book updated", etag=generate_etag(book))

@app.route('/api/v1/books/<book_id>', methods=['DELETE'])
@token_required
@limiter.limit("10 per minute")
def delete_book(current_user, book_id):
    with tracer.start_as_current_span("delete_book_from_db") as span:
        span.set_attribute("book.id", book_id)
        
        result = books_col.delete_one({"_id": ObjectId(book_id)})
        
        if result.deleted_count == 0:
            span.set_attribute("book.found", False)
            return error_response("Book not found", 404)
        
        span.set_attribute("book.found", True)
        span.set_attribute("book.deleted", True)
    
    return success_response(None, "Book deleted")

# ------------------ Health Check ------------------

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring"""
    with tracer.start_as_current_span("health_check") as span:
        try:
            # Check MongoDB connection
            client.admin.command('ping')
            span.set_attribute("mongodb.healthy", True)
            
            return success_response({
                "status": "healthy",
                "mongodb": "connected",
                "tracing": "enabled"
            })
        except Exception as e:
            span.set_attribute("mongodb.healthy", False)
            span.set_attribute("error", str(e))
            return error_response(f"Health check failed: {str(e)}", 503)

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
    return jsonify({
        "message": "Book Management API",
        "docs": "/docs",
        "health": "/health"
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003)