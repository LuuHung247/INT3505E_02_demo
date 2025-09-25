from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import graphene
from graphene import ObjectType, String, Int, Field, List, Mutation

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:240724@localhost/soa_demo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Model ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

# --- GraphQL Type ---
class UserType(ObjectType):
    id = Int()
    name = String()
    email = String()

    @staticmethod
    def from_model(user):
        return UserType(id=user.id, name=user.name, email=user.email)

# --- Queries ---
class Query(ObjectType):
    all_users = List(UserType)
    user = Field(UserType, id=Int(required=True))

    def resolve_all_users(root, info):
        return [UserType.from_model(u) for u in User.query.all()]

    def resolve_user(root, info, id):
        user = User.query.get(id)
        if user:
            return UserType.from_model(user)
        return None

# --- Mutations ---
class CreateUser(Mutation):
    class Arguments:
        name = String(required=True)
        email = String(required=True)

    ok = String()
    user = Field(UserType)

    def mutate(root, info, name, email):
        if User.query.filter_by(email=email).first():
            raise Exception("Email already exists")
        user = User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
        return CreateUser(ok="User created", user=UserType.from_model(user))

class UpdateUser(Mutation):
    class Arguments:
        id = Int(required=True)
        name = String()
        email = String()

    ok = String()
    user = Field(UserType)

    def mutate(root, info, id, name=None, email=None):
        user = User.query.get(id)
        if not user:
            raise Exception("User not found")
        if name:
            user.name = name
        if email:
            user.email = email
        db.session.commit()
        return UpdateUser(ok="User updated", user=UserType.from_model(user))

class DeleteUser(Mutation):
    class Arguments:
        id = Int(required=True)

    ok = String()

    def mutate(root, info, id):
        user = User.query.get(id)
        if not user:
            raise Exception("User not found")
        db.session.delete(user)
        db.session.commit()
        return DeleteUser(ok="User deleted")

class Mutation(ObjectType):
    create_user = CreateUser.Field()
    update_user = UpdateUser.Field()
    delete_user = DeleteUser.Field()

# --- Schema ---
schema = graphene.Schema(query=Query, mutation=Mutation)

# --- Flask Route ---
@app.route("/graphql", methods=["POST"])
def graphql_view():
    data = request.get_json()
    result = schema.execute_sync(
        data.get("query"),
        variable_values=data.get("variables")
    )
    response = {}
    if result.errors:
        response["errors"] = [str(e) for e in result.errors]
    if result.data:
        response["data"] = result.data
    return jsonify(response)

# --- Main ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)
