from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import hashlib
import json
import jwt
import datetime
from functools import wraps
from flask_swagger_ui import get_swaggerui_blueprint
app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_here'  # Dùng để mã hóa JWT

db = SQLAlchemy(app)

# ------------------ Model ------------------
class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "available": self.available
        }


class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    join_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "join_date": self.join_date.strftime("%Y-%m-%d %H:%M:%S")
        }
    # Quan hệ: Một member có thể mượn nhiều sách
    book_borrowed = db.relationship("BookBorrowed", back_populates="member")
class BookBorrowed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('member.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    return_date = db.Column(db.DateTime, nullable=True)

    member = db.relationship("Member", back_populates="book_borrowed")
    book = db.relationship("Book", backref="book_borrowed")

    __table_args__ = (
        db.UniqueConstraint('book_id', 'return_date', name='unique_active_borrow'),
    )
    def to_dict(self):
        return {
            "id": self.id,
            "member_id": self.member_id,
            "book_id": self.book_id,
            "borrow_date": self.borrow_date.strftime("%Y-%m-%d %H:%M:%S"),
            "return_date": self.return_date.strftime("%Y-%m-%d %H:%M:%S") if self.return_date else None
        }
# ------------------ Helper functions ------------------

def generate_etag(data_dict):
    """Tạo ETag dựa trên hash MD5 của dữ liệu JSON."""
    data_str = json.dumps(data_dict, sort_keys=True)
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
    response = jsonify({"status": "error", "data": None, "message": message})
    response.headers["Content-Type"] = "application/json"
    return response

# ------------------ AUTH ------------------

# Decorator xác thực JWT
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
    if username == 'admin' and password == '123456':  # Demo
        token = jwt.encode({
            'user': username,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
        }, app.config['SECRET_KEY'], algorithm="HS256")
        return success_response({"token": token}, "Login successful")
    return error_response("Invalid credentials", 401)

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



# ------------------ Swagger UI ------------------

# Đường dẫn file swagger.yaml trong thư mục static
SWAGGER_URL = '/docs'
API_URL = '/static/swagger.yaml'

swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Book Management API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Route để phục vụ swagger.yaml từ thư mục static
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(app.root_path, 'static'), filename)


@app.route('/')
def home():
    return 'Swagger UI available at /docs'

# ------------------ Main ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
