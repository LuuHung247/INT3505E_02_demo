# app_cognito.py
import os
import json
import hashlib
import datetime
import base64
import requests
import urllib.parse
from dotenv import load_dotenv
from functools import wraps

from flask import (
    Flask, request, jsonify, make_response, redirect, url_for, session, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_swagger_ui import get_swaggerui_blueprint

from authlib.integrations.flask_client import OAuth
from authlib.jose import JsonWebKey, jwt as auth_jwt
from authlib.jose.errors import JoseError

# ---------- Load env ----------
load_dotenv()

# ---------- App setup ----------
app = Flask(__name__)
CORS(app)

app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI', 'sqlite:///demo.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
# ---------- Cognito config ----------
COGNITO_REGION = os.getenv('COGNITO_REGION')
COGNITO_USER_POOL_ID = os.getenv('COGNITO_USER_POOL_ID')
COGNITO_CLIENT_ID = os.getenv('COGNITO_CLIENT_ID')
COGNITO_CLIENT_SECRET = os.getenv('COGNITO_CLIENT_SECRET') or None
COGNITO_DOMAIN = os.getenv('COGNITO_DOMAIN')
COGNITO_REDIRECT_URI = os.getenv('COGNITO_REDIRECT_URI', 'http://localhost:5001/callback')
COGNITO_LOGOUT_REDIRECT_URI = os.getenv('COGNITO_LOGOUT_REDIRECT_URI', 'http://localhost:5001/')

COGNITO_ISSUER = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
COGNITO_OIDC_CONF = f"{COGNITO_ISSUER}/.well-known/openid-configuration"
COGNITO_JWKS_URL = f"{COGNITO_ISSUER}/.well-known/jwks.json"
COGNITO_AUTHORIZE_URL = f"https://{COGNITO_DOMAIN}.auth.{COGNITO_REGION}.amazoncognito.com/oauth2/authorize"
COGNITO_TOKEN_URL = f"https://{COGNITO_DOMAIN}.auth.{COGNITO_REGION}.amazoncognito.com/oauth2/token"
COGNITO_USERINFO_URL = f"https://{COGNITO_DOMAIN}.auth.{COGNITO_REGION}.amazoncognito.com/oauth2/userInfo"
COGNITO_LOGOUT_URL = f"https://{COGNITO_DOMAIN}.auth.{COGNITO_REGION}.amazoncognito.com/logout"

# ---------- OAuth (Authlib) ----------
oauth = OAuth(app)
oauth.register(
    name='cognito',
    client_id=COGNITO_CLIENT_ID,
    client_secret=COGNITO_CLIENT_SECRET,
    server_metadata_url=COGNITO_OIDC_CONF,
    client_kwargs={'scope': 'openid email profile'}
)

# ---------- JWKS cache ----------
_jwks_cache = {"jwks": None, "fetched_at": None}
def get_jwks():
    now = datetime.datetime.utcnow()
    if _jwks_cache["jwks"] and _jwks_cache["fetched_at"]:
        if (now - _jwks_cache["fetched_at"]).total_seconds() < 3600:
            return _jwks_cache["jwks"]
    resp = requests.get(COGNITO_JWKS_URL)
    resp.raise_for_status()
    jwks = resp.json()
    _jwks_cache["jwks"] = jwks
    _jwks_cache["fetched_at"] = now
    return jwks

# ---------- Models (kept minimal for your API) ----------
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=True)
    def to_dict(self):
        return {"id": self.id, "title": self.title, "author": self.author, "available": self.available}

class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    join_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    book_borrowed = db.relationship("BookBorrowed", back_populates="member")
    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email, "join_date": self.join_date.strftime("%Y-%m-%d %H:%M:%S")}

class BookBorrowed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    return_date = db.Column(db.DateTime, nullable=True)
    member = db.relationship("Member", back_populates="book_borrowed")
    book = db.relationship("Book", backref="book_borrowed")
    __table_args__ = (db.UniqueConstraint('book_id', 'return_date', name='unique_active_borrow'),)
    def to_dict(self):
        return {
            "id": self.id,
            "member_id": self.member_id,
            "book_id": self.book_id,
            "borrow_date": self.borrow_date.strftime("%Y-%m-%d %H:%M:%S"),
            "return_date": self.return_date.strftime("%Y-%m-%d %H:%M:%S") if self.return_date else None
        }

# ---------- Helpers ----------
def generate_etag(data_dict):
    data_str = json.dumps(data_dict, sort_keys=True)
    return hashlib.md5(data_str.encode('utf-8')).hexdigest()

def success_response(data=None, message=None, status_code=200, etag=None):
    response = make_response(jsonify({"status": "success", "data": data, "message": message}), status_code)
    if etag:
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "private, max-age=120"
    return response

def error_response(message, status_code=400):
    response = jsonify({"status": "error", "data": None, "message": message})
    response.headers["Content-Type"] = "application/json"
    return response, status_code

# ---------- Auth: verify Cognito access token ----------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', None)
        if not auth or not auth.startswith('Bearer '):
            return error_response("Token is missing", 401)
        token = auth.split()[1]
        try:
            jwks = get_jwks()
            key_set = JsonWebKey.import_key_set(jwks)
            claims = auth_jwt.decode(token, key_set)
            # Validate standard claims
            iss = claims.get('iss')
            if iss != COGNITO_ISSUER:
                return error_response("Invalid token issuer", 401)
            aud = claims.get('aud') or claims.get('client_id')
            if isinstance(aud, list):
                if COGNITO_CLIENT_ID not in aud:
                    return error_response("Invalid token audience", 401)
            else:
                if aud != COGNITO_CLIENT_ID:
                    return error_response("Invalid token audience", 401)
            exp = claims.get('exp')
            if exp and datetime.datetime.utcnow().timestamp() > int(exp):
                return error_response("Token expired", 401)
            current_user = claims.get('email') or claims.get('username') or claims.get('sub')
        except JoseError as e:
            return error_response(f"Invalid token: {str(e)}", 401)
        except Exception as e:
            return error_response(f"Token verification error: {str(e)}", 401)
        return f(current_user, *args, **kwargs)
    return decorated

# ---------- Cognito login / callback / refresh / logout ----------
@app.route('/login')
def login():
    # redirect to Cognito hosted UI
    redirect_uri = COGNITO_REDIRECT_URI
    return oauth.cognito.authorize_redirect(redirect_uri)

@app.route('/callback')
def callback():
    """
    Cognito will redirect here with ?code=...
    We exchange code -> tokens (access, id, refresh), fetch userinfo,
    store them in session and return tokens JSON so you can copy to Postman.
    """
    # Exchange code for tokens (Authlib handles client_secret if configured)
    token = oauth.cognito.authorize_access_token()  # performs token request
    if not token:
        return error_response("Failed to obtain token from Cognito", 500)

    # token is a dict with access_token, refresh_token (if allowed), id_token, expires_at...
    # Try fetch userinfo (some configs may not allow userinfo)
    userinfo = {}
    try:
        userinfo = oauth.cognito.userinfo(token=token)
    except Exception:
        # ignore if userinfo endpoint is not available or scope not granted
        userinfo = {}

    # Save into server-side session for convenience (short-lived)
    session['token'] = token
    session['userinfo'] = userinfo
    session.permanent = False  # do not persist too long

    # Return JSON to user (useful to copy tokens for Postman)
    return jsonify({
        "message": "Login successful. Copy access_token to call /api endpoints.",
        "token": token,
        "userinfo": userinfo
    })

@app.route('/refresh', methods=['POST'])
def refresh():
    """
    Refresh access token using refresh_token.
    - If session has token.refresh_token it will be used.
    - Or client can send JSON { "refresh_token": "<...>" } in body.
    """
    body = request.get_json(silent=True) or {}
    provided_rt = body.get('refresh_token')

    # prefer explicit provided refresh token
    refresh_token = provided_rt or (session.get('token') or {}).get('refresh_token')
    if not refresh_token:
        return error_response("No refresh_token available", 401)

    # Prepare token request per OAuth2 spec for refresh_token grant
    data = {
        'grant_type': 'refresh_token',
        'client_id': COGNITO_CLIENT_ID,
        'refresh_token': refresh_token
    }
    headers = {}
    # Cognito requires client secret in Basic auth if client has secret
    if COGNITO_CLIENT_SECRET:
        creds = f"{COGNITO_CLIENT_ID}:{COGNITO_CLIENT_SECRET}"
        b64 = base64.b64encode(creds.encode()).decode()
        headers['Authorization'] = f"Basic {b64}"

    resp = requests.post(COGNITO_TOKEN_URL, data=data, headers=headers)
    if resp.status_code != 200:
        return error_response(f"Refresh failed: {resp.status_code} {resp.text}", 401)

    new_token = resp.json()
    # The response may contain new access_token and id_token; Cognito does not always return a new refresh_token
    # Update session token (merge)
    existing = session.get('token') or {}
    merged = {**existing, **new_token}
    session['token'] = merged

    return jsonify({
        "message": "Token refreshed",
        "token": new_token
    })

@app.route('/logout')
def logout():
    session.clear()
    return redirect(
        f"{COGNITO_LOGOUT_URL}"
        f"?client_id={COGNITO_CLIENT_ID}"
        f"&logout_uri={COGNITO_LOGOUT_REDIRECT_URI}"
    )




@app.route('/me/token')
def me_token():
    token = session.get('token')
    if not token:
        return error_response("No token in session. Please login at /login", 401)
    return jsonify(token)
# ------------------ Book API ------------------

@app.route('/api/v1/books', methods=['GET'])
@token_required
def get_books(current_user):
    available = request.args.get('available')
    title = request.args.get('title')
    author = request.args.get('author')
    limit = int(request.args.get('limit', 10))
    cursor = request.args.get('cursor', type=int)

    query = Book.query

    if available is not None:
        query = query.filter_by(available=(available.lower() == 'true'))
    if title:
        query = query.filter(Book.title.ilike(f"%{title}%"))
    if author:
        query = query.filter(Book.author.ilike(f"%{author}%"))
    if cursor:
        query = query.filter(Book.id > cursor)

    books = query.order_by(Book.id.asc()).limit(limit + 1).all()

    has_next = len(books) > limit
    books_to_return = books[:limit]

    next_cursor = books_to_return[-1].id if has_next else None
    book_list = [b.to_dict() for b in books_to_return]

    pagination = {
        "limit": limit,
        "next_cursor": next_cursor
    }

    etag = generate_etag(book_list)
    return success_response({"books": book_list, "pagination": pagination}, "Books fetched successfully", etag=etag)


@app.route('/api/v1/books/<int:book_id>', methods=['GET'])
@token_required
def get_book(current_user, book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)

    book_data = book.to_dict()
    etag = generate_etag(book_data)
    client_etag = request.headers.get('If-None-Match')
    if client_etag == etag:
        return '', 304

    return success_response(book_data, etag=etag)

@app.route('/api/v1/books', methods=['POST'])
@token_required
def create_book(current_user):
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return error_response("Missing title or author", 400)
    new_book = Book(title=data['title'], author=data['author'])
    db.session.add(new_book)
    db.session.commit()
    book_data = new_book.to_dict()
    etag = generate_etag(book_data)
    return success_response(book_data, "Book created", 201, etag)

@app.route('/api/v1/books/<int:book_id>', methods=['PUT'])
@token_required
def update_book(current_user, book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)

    data = request.get_json()
    if not data:
        return error_response("No data provided", 400)

    # Cập nhật thông tin cơ bản
    if "title" in data:
        book.title = data["title"]
    if "author" in data:
        book.author = data["author"]

    # Xử lý borrow/return với ràng buộc hợp lệ
    action = "Book info updated"
    if "available" in data:
        new_status = bool(data["available"])

        # Nếu client yêu cầu mượn mà sách đang bị mượn
        if not new_status and not book.available:
            return error_response("Book is already borrowed", 400)

        # Nếu client yêu cầu trả mà sách đang sẵn có
        if new_status and book.available:
            return error_response("Book is already available", 400)

        # Nếu hợp lệ thì cập nhật trạng thái
        if book.available and not new_status:
            book.available = False
            action = "Book borrowed"
        elif not book.available and new_status:
            book.available = True
            action = "Book returned"

    db.session.commit()

    book_data = book.to_dict()
    etag = generate_etag(book_data)
    return success_response(book_data, action, etag=etag)


@app.route('/api/v1/books/<int:book_id>', methods=['DELETE'])
@token_required
def delete_book(current_user, book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)
    db.session.delete(book)
    db.session.commit()
    return success_response(None, "Book deleted")

# ------------------ Member API ------------------

@app.route('/api/v1/members', methods=['GET'])
@token_required
def get_members(current_user):
    name = request.args.get('name')
    limit = int(request.args.get('limit', 10))
    cursor = request.args.get('cursor', type=int)

    query = Member.query
    if name:
        query = query.filter(Member.name.ilike(f"%{name}%"))
    if cursor:
        query = query.filter(Member.id > cursor)

    members = query.order_by(Member.id.asc()).limit(limit + 1).all()
    has_next = len(members) > limit
    members_to_return = members[:limit]

    next_cursor = members_to_return[-1].id if has_next else None
    data = [m.to_dict() for m in members_to_return]

    pagination = {
        "limit": limit,
        "next_cursor": next_cursor
    }

    return success_response({"members": data, "pagination": pagination}, "Members fetched successfully")



@app.route('/api/v1/members/<int:member_id>', methods=['GET'])
@token_required
def get_member(current_user, member_id):
    member = db.session.get(Member, member_id)
    if not member:
        return error_response("Member not found", 404)

    member_data = member.to_dict()
    etag = generate_etag(member_data)
    client_etag = request.headers.get('If-None-Match')
    if client_etag == etag:
        return '', 304

    return success_response(member_data, "Member fetched successfully", etag=etag)


@app.route('/api/v1/members', methods=['POST'])
@token_required
def create_member(current_user):
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        return error_response("Missing name or email", 400)

    existing_member = Member.query.filter_by(email=data['email']).first()
    if existing_member:
        return error_response("Email already exists", 400)

    new_member = Member(name=data['name'], email=data['email'])
    db.session.add(new_member)
    db.session.commit()

    member_data = new_member.to_dict()
    etag = generate_etag(member_data)
    return success_response(member_data, "Member created successfully", 201, etag)


@app.route('/api/v1/members/<int:member_id>', methods=['PUT'])
@token_required
def update_member(current_user, member_id):
    member = db.session.get(Member, member_id)
    if not member:
        return error_response("Member not found", 404)

    data = request.get_json()
    if not data:
        return error_response("No data provided", 400)

    if "name" in data:
        member.name = data["name"]
    if "email" in data:
        # Kiểm tra email trùng lặp
        existing = Member.query.filter(Member.email == data["email"], Member.id != member_id).first()
        if existing:
            return error_response("Email already exists", 400)
        member.email = data["email"]

    db.session.commit()

    member_data = member.to_dict()
    etag = generate_etag(member_data)
    return success_response(member_data, "Member updated successfully", etag=etag)


@app.route('/api/v1/members/<int:member_id>', methods=['DELETE'])
@token_required
def delete_member(current_user, member_id):
    member = db.session.get(Member, member_id)
    if not member:
        return error_response("Member not found", 404)

    db.session.delete(member)
    db.session.commit()
    return success_response(None, "Member deleted successfully")


# ------------------ Book Borrowed API ------------------
@app.route('/api/v1/books-borrowed', methods=['GET'])
@token_required
def get_books_borrowed(current_user):
    member_id = request.args.get('member_id', type=int)
    limit = int(request.args.get('limit', 10))
    cursor = request.args.get('cursor', type=int)

    query = BookBorrowed.query
    if member_id:
        query = query.filter_by(member_id=member_id)
    if cursor:
        query = query.filter(BookBorrowed.id > cursor)

    records = query.order_by(BookBorrowed.id.asc()).limit(limit + 1).all()
    has_next = len(records) > limit
    records_to_return = records[:limit]

    next_cursor = records_to_return[-1].id if has_next else None
    data = [r.to_dict() for r in records_to_return]

    pagination = {
        "limit": limit,
        "next_cursor": next_cursor
    }

    return success_response({"books_borrowed": data, "pagination": pagination}, "Borrow records fetched successfully")



@app.route('/api/v1/books-borrowed', methods=['POST'])
@token_required
def create_book_borrowed(current_user):
    data = request.get_json()
    member_id = data.get('member_id')
    book_id = data.get('book_id')

    if not member_id or not book_id:
        return error_response("Missing member_id or book_id", 400)

    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)

    # Kiểm tra nếu sách đang bị mượn (chưa có return_date)
    existing_borrow = BookBorrowed.query.filter_by(book_id=book_id, return_date=None).first()
    if existing_borrow:
        return error_response("Book is already borrowed", 400)

    new_borrow = BookBorrowed(member_id=member_id, book_id=book_id)
    book.available = False

    db.session.add(new_borrow)
    db.session.commit()
    return success_response(new_borrow.to_dict(), "Book borrowed successfully", 201)


@app.route('/api/v1/books-borrowed/<int:borrow_id>', methods=['PUT'])
@token_required
def return_book(current_user, borrow_id):
    record = db.session.get(BookBorrowed, borrow_id)
    if not record:
        return error_response("Borrow record not found", 404)

    if record.return_date:
        return error_response("Book already returned", 400)

    record.return_date = datetime.datetime.utcnow()
    record.book.available = True
    db.session.commit()

    return success_response(record.to_dict(), "Book returned successfully")


@app.route('/api/v1/books-borrowed/<int:borrow_id>', methods=['DELETE'])
@token_required
def delete_borrow_record(current_user, borrow_id):
    record = db.session.get(BookBorrowed, borrow_id)
    if not record:
        return error_response("Borrow record not found", 404)

    db.session.delete(record)
    db.session.commit()
    return success_response(None, "Borrow record deleted successfully")

# ---------- Swagger UI ----------
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

# ---------- Main ----------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
