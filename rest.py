from flask import Flask, request, jsonify, url_for, render_template_string
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "_links": {
                "self": {"href": url_for('get_user', user_id=self.id, _external=True)},
                "update": {"href": url_for('put_user', user_id=self.id, _external=True), "method": "PUT"},
                "patch": {"href": url_for('patch_user', user_id=self.id, _external=True), "method": "PATCH"},
                "delete": {"href": url_for('delete_user', user_id=self.id, _external=True), "method": "DELETE"},
                "all_users": {"href": url_for('get_users', _external=True), "method": "GET"},
                "create": {"href": url_for('create_user', _external=True), "method": "POST"}
            }
        }

# ------------------ User API ------------------

@app.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify({
        "status": "success",
        "data": [u.to_dict() for u in users],
        "_links": {
            "create": {"href": url_for('create_user', _external=True), "method": "POST"}
        }
    }), 200

@app.route('/users/<int:user_id>', methods=['GET'])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    return jsonify({"status": "success", "data": user.to_dict()}), 200

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

@app.route('/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({
        "status": "deleted",
        "_links": {
            "all_users": {"href": url_for('get_users', _external=True), "method": "GET"},
            "create": {"href": url_for('create_user', _external=True), "method": "POST"}
        }
    }), 200

# ------------------ Code on Demand ------------------

@app.route("/client_code.js")
def client_code():
    js_code = """
export async function showUser(userId) {
    try {
        const res = await fetch(`/users/${userId}`);
        if (!res.ok) throw new Error('User not found');
        const data = await res.json();
        const user = data.data;
        alert(`User info:\\nID: ${user.id}\\nName: ${user.name}\\nEmail: ${user.email}`);
    } catch(e) {
        alert(e.message);
    }
}

export function greet(name) {
    alert(`Hello ${name}! This message comes from server code.`);
}
"""
    return js_code, 200, {"Content-Type": "application/javascript"}

@app.route("/cod_demo")
def cod_demo():
    html = """
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Code on Demand Demo</title></head>
<body>
    <h1>Code on Demand + User API Demo</h1>
    <input type="number" id="userId" placeholder="Enter user ID" />
    <button id="showBtn">Show User</button>
    <button id="greetBtn">Greet</button>

    <script type="module">
        document.getElementById('greetBtn').addEventListener('click', async () => {
            const mod = await import('/client_code.js');
            mod.greet('Alice');
        });

        document.getElementById('showBtn').addEventListener('click', async () => {
            const mod = await import('/client_code.js');
            const id = document.getElementById('userId').value;
            if(id) mod.showUser(id);
        });
    </script>
</body>
</html>
"""
    return render_template_string(html)

# --- Main ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
