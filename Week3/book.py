from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

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

# ------------------ Response helper ------------------

def success_response(data=None, message=None, status_code=200):
    return jsonify({"status": "success", "data": data, "message": message}), status_code

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
    return success_response([b.to_dict() for b in books])

@app.route('/api/v1/books/<int:book_id>', methods=['GET'])
def get_book(book_id):
    book = db.session.get(Book, book_id)
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
    return success_response(book.to_dict(), "Book updated")

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
    return success_response(book.to_dict(), "Book borrowed")

@app.route('/api/v1/books/<int:book_id>/return', methods=['POST'])
def return_book(book_id):
    book = db.session.get(Book, book_id)
    if not book:
        return error_response("Book not found", 404)
    if book.available:
        return error_response("Book is already available", 400)
    book.available = True
    db.session.commit()
    return success_response(book.to_dict(), "Book returned")


# ------------------ Main ------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
