from flask import Flask, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import hashlib
import json

app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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
    return jsonify({"status": "error", "data": None, "message": message}), status_code

# ------------------ Book API ------------------

@app.route('/api/v1/books', methods=['GET'])
def get_books():
    available = request.args.get('available')
    query = Book.query
    if available is not None:
        query = query.filter_by(available=(available.lower() == 'true'))
    books = query.all()
    book_list = [b.to_dict() for b in books]
    etag = generate_etag(book_list)

    # Kiểm tra ETag từ client
    client_etag = request.headers.get('If-None-Match')
    if client_etag == etag:
        return '', 304  # Không có thay đổi

    return success_response(book_list, etag=etag)

@app.route('/api/v1/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
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
def create_book():
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
def update_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)

    data = request.get_json()
    if "title" in data:
        book.title = data["title"]
    if "author" in data:
        book.author = data["author"]
    if "available" in data:
        book.available = bool(data["available"])
    db.session.commit()

    book_data = book.to_dict()
    etag = generate_etag(book_data)
    return success_response(book_data, "Book updated", etag=etag)

@app.route('/api/v1/books/<int:book_id>', methods=['DELETE'])
def delete_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)
    db.session.delete(book)
    db.session.commit()
    return success_response(None, "Book deleted")

# -------- Borrow / Return without borrow table --------

@app.route('/api/v1/books/<int:book_id>/borrow', methods=['POST'])
def borrow_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)
    if not book.available:
        return error_response("Book is already borrowed", 400)
    book.available = False
    db.session.commit()
    book_data = book.to_dict()
    etag = generate_etag(book_data)
    return success_response(book_data, "Book borrowed", etag=etag)

@app.route('/api/v1/books/<int:book_id>/return', methods=['POST'])
def return_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)
    if book.available:
        return error_response("Book is already available", 400)
    book.available = True
    db.session.commit()
    book_data = book.to_dict()
    etag = generate_etag(book_data)
    return success_response(book_data, "Book returned", etag=etag)

# ------------------ Main ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
