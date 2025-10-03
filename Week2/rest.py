from flask import Flask, request, jsonify, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ------------------ Models ------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    borrows = db.relationship('Borrow', backref='user', lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}


class Book(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    author = db.Column(db.String(100), nullable=False)
    available = db.Column(db.Boolean, default=True)
    borrows = db.relationship('Borrow', backref='book', lazy=True)

    def to_dict(self):
        return {"id": self.id, "title": self.title, "author": self.author, "available": self.available}


class Borrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    book_id = db.Column(db.Integer, db.ForeignKey('book.id'), nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow)
    return_date = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user": {"id": self.user.id, "name": self.user.name},
            "book": {"id": self.book.id, "title": self.book.title},
            "borrow_date": self.borrow_date.isoformat(),
            "return_date": self.return_date.isoformat() if self.return_date else None
        }

# ------------------ Response helper ------------------

def success_response(data=None, message=None, status_code=200):
    return jsonify({"status": "success", "data": data, "message": message}), status_code

def error_response(message, status_code=400):
    return jsonify({"status": "error", "data": None, "message": message}), status_code

# ------------------ User API ------------------

@app.route('/api/v1/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return success_response([u.to_dict() for u in users])

@app.route('/api/v1/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return error_response("User not found", 404)
    return success_response(user.to_dict())

@app.route('/api/v1/users', methods=['POST'])
def create_user():
    data = request.get_json()
    if not data or not data.get('name') or not data.get('email'):
        return error_response("Missing name or email", 400)
    if User.query.filter_by(email=data['email']).first():
        return error_response("Email already exists", 409)
    new_user = User(name=data['name'], email=data['email'])
    db.session.add(new_user)
    db.session.commit()
    return success_response(new_user.to_dict(), "User created", 201)

@app.route('/api/v1/users/<int:user_id>/borrows', methods=['GET'])
def get_user_borrows(user_id):
    user = User.query.get(user_id)
    if not user:
        return error_response("User not found", 404)
    borrows = Borrow.query.filter_by(user_id=user_id).all()
    return success_response([b.to_dict() for b in borrows])

# ------------------ Book API ------------------

@app.route('/api/v1/books', methods=['GET'])
def get_books():
    available = request.args.get('available')
    query = Book.query
    if available is not None:
        query = query.filter_by(available=(available.lower() == 'true'))
    books = query.all()
    return success_response([b.to_dict() for b in books])

@app.route('/api/v1/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = Book.query.get(book_id)
    if not book:
        return error_response("Book not found", 404)
    return success_response(book.to_dict())

@app.route('/api/v1/books', methods=['POST'])
def create_book():
    data = request.get_json()
    if not data or not data.get('title') or not data.get('author'):
        return error_response("Missing title or author", 400)
    new_book = Book(title=data['title'], author=data['author'])
    db.session.add(new_book)
    db.session.commit()
    return success_response(new_book.to_dict(), "Book created", 201)

# ------------------ Borrow API ------------------

@app.route('/api/v1/borrows', methods=['POST'])
def borrow_book():
    data = request.get_json()
    if not data or not data.get('user_id') or not data.get('book_id'):
        return error_response("Missing user_id or book_id", 400)
    user = User.query.get(data['user_id'])
    book = Book.query.get(data['book_id'])
    if not user or not book:
        return error_response("User or Book not found", 404)
    if not book.available:
        return error_response("Book already borrowed", 400)
    borrow = Borrow(user_id=user.id, book_id=book.id)
    book.available = False
    db.session.add(borrow)
    db.session.commit()
    return success_response(borrow.to_dict(), "Book borrowed", 201)

@app.route('/api/v1/borrows', methods=['GET'])
def get_borrows():
    user_id = request.args.get('user_id')
    returned = request.args.get('returned')
    query = Borrow.query
    if user_id:
        query = query.filter_by(user_id=int(user_id))
    if returned is not None:
        if returned.lower() == 'true':
            query = query.filter(Borrow.return_date.isnot(None))
        else:
            query = query.filter(Borrow.return_date.is_(None))
    borrows = query.all()
    return success_response([b.to_dict() for b in borrows])

@app.route('/api/v1/borrows/<int:borrow_id>', methods=['GET'])
def get_borrow(borrow_id):
    borrow = Borrow.query.get(borrow_id)
    if not borrow:
        return error_response("Borrow record not found", 404)
    return success_response(borrow.to_dict())

@app.route('/api/v1/borrows/<int:borrow_id>/return', methods=['POST'])
def return_book(borrow_id):
    borrow = Borrow.query.get(borrow_id)
    if not borrow:
        return error_response("Borrow record not found", 404)
    if borrow.return_date:
        return error_response("Book already returned", 400)
    borrow.return_date = datetime.utcnow()
    borrow.book.available = True
    db.session.commit()
    return success_response(borrow.to_dict(), "Book returned")

# ------------------ Main ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
