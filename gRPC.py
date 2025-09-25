import grpc
from concurrent import futures
import time
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import user_pb2
import user_pb2_grpc

# SQLAlchemy setup
DATABASE_URL = "mysql+pymysql://root:240724@localhost/soa_demo"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Model
class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    email = Column(String(100), unique=True, nullable=False)

# Create tables
Base.metadata.create_all(bind=engine)

# gRPC Service
class UserService(user_pb2_grpc.UserServiceServicer):

    def GetUser(self, request, context):
        db = SessionLocal()
        user = db.query(User).filter(User.id == request.id).first()
        db.close()
        if not user:
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return user_pb2.UserResponse()
        return user_pb2.UserResponse(
            user=user_pb2.User(id=user.id, name=user.name, email=user.email),
            message="Success"
        )

    def GetUsers(self, request, context):
        db = SessionLocal()
        users = db.query(User).all()
        db.close()
        return user_pb2.UsersResponse(
            users=[user_pb2.User(id=u.id, name=u.name, email=u.email) for u in users]
        )

    def CreateUser(self, request, context):
        db = SessionLocal()
        user = User(name=request.name, email=request.email)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()
        return user_pb2.UserResponse(
            user=user_pb2.User(id=user.id, name=user.name, email=user.email),
            message="User created"
        )

    def UpdateUser(self, request, context):
        db = SessionLocal()
        user = db.query(User).filter(User.id == request.id).first()
        if not user:
            db.close()
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return user_pb2.UserResponse()
        user.name = request.name
        user.email = request.email
        db.commit()
        db.refresh(user)
        db.close()
        return user_pb2.UserResponse(
            user=user_pb2.User(id=user.id, name=user.name, email=user.email),
            message="User updated"
        )

    def DeleteUser(self, request, context):
        db = SessionLocal()
        user = db.query(User).filter(User.id == request.id).first()
        if not user:
            db.close()
            context.set_details("User not found")
            context.set_code(grpc.StatusCode.NOT_FOUND)
            return user_pb2.DeleteResponse(success=False, message="User not found")
        db.delete(user)
        db.commit()
        db.close()
        return user_pb2.DeleteResponse(success=True, message="User deleted")

# Run server
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    user_pb2_grpc.add_UserServiceServicer_to_server(UserService(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("gRPC server running on port 50051...")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()
