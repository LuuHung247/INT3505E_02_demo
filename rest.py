from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#Model 
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "email": self.email}

#API Endpoints

#GET all users
@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify({"status": "success", "data": [u.to_dict() for u in users]}), 200

#GET single user
@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    return jsonify({"status": "success", "data": user.to_dict()}), 200

#POST user
@app.route('/users', methods=['POST'])
def create_user():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400
    data = request.get_json()
    if not data.get('name') or not data.get('email'):
        return jsonify({"status": "error", "message": "Missing name or email"}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({"status": "error", "message": "Email already exists"}), 409
    new_user = User(name=data['name'], email=data['email'])
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"status": "success", "data": new_user.to_dict()}), 201

# PATCH update partial (name/email)
@app.route('/users/<int:user_id>', methods=['PATCH'])
def patch_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    data = request.get_json()
    if data.get('name'):
        user.name = data['name']
    if data.get('email'):
        user.email = data['email']
    db.session.commit()
    return jsonify({"status": "success", "data": user.to_dict()}), 200

# PUT full update
@app.route('/users/<int:user_id>', methods=['PUT'])
def put_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    data = request.get_json()
    if not data.get('name') or not data.get('email'):
        return jsonify({"status": "error", "message": "Missing name or email"}), 400
    user.name = data['name']
    user.email = data['email']
    db.session.commit()
    return jsonify({"status": "success", "data": user.to_dict()}), 200

# DELETE user
@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return '', 204

# --- Main ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
