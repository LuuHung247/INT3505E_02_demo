from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import graphene

# ---------------- Database setup ----------------
SQLALCHEMY_DATABASE_URL = "mysql+pymysql://root:240724@localhost/soa_demo"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserModel(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)

Base.metadata.create_all(bind=engine)

# ---------------- Graphene GraphQL ----------------
class UserType(graphene.ObjectType):
    id = graphene.Int()
    name = graphene.String()
    email = graphene.String()

def get_user_from_db(user_id):
    db: Session = SessionLocal()
    u = db.query(UserModel).filter(UserModel.id == user_id).first()
    db.close()
    if u:
        return UserType(id=u.id, name=u.name, email=u.email)
    return None

def get_all_users_from_db():
    db: Session = SessionLocal()
    users = db.query(UserModel).all()
    db.close()
    return [UserType(id=u.id, name=u.name, email=u.email) for u in users]

class Query(graphene.ObjectType):
    user = graphene.Field(UserType, id=graphene.Int(required=True))
    users = graphene.List(UserType)

    def resolve_user(root, info, id):
        return get_user_from_db(id)

    def resolve_users(root, info):
        return get_all_users_from_db()

schema = graphene.Schema(query=Query)

# ---------------- FastAPI App ----------------
app = FastAPI()

# Endpoint GraphQL POST cho Postman
@app.post("/graphql")
async def graphql_post(request: Request):
    body = await request.json()
    query = body.get("query")
    variables = body.get("variables")
    result = schema.execute(query, variables=variables)
    response = {}
    if result.errors:
        response["errors"] = [str(e) for e in result.errors]
    if result.data:
        response["data"] = result.data
    return JSONResponse(response)

# Optional: simple GET cho kiểm tra
@app.get("/graphql")
def graphql_get():
    return JSONResponse({"message": "POST GraphQL queries here"})

# Run: uvicorn graphQl:app --reload --port 5001
