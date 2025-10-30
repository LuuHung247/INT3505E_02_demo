import connexion
import jwt
import datetime
import os
from typing import Dict, Tuple, Union
from dotenv import load_dotenv

from openapi_server.models.api_v1_login_post200_response import ApiV1LoginPost200Response  # noqa: E501
from openapi_server.models.api_v1_login_post_request import ApiV1LoginPostRequest  # noqa: E501
from openapi_server import util

# ------------------ Load environment ------------------
load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY", "defaultsecret")


# ------------------ Login API ------------------
def api_v1_login_post(body):  # noqa: E501
    """Login to obtain JWT token"""

    # 1. Kiểm tra định dạng request
    if not connexion.request.is_json:
        return {"message": "Invalid request format"}, 400

    # 2. Parse dữ liệu từ model OpenAPI
    data = ApiV1LoginPostRequest.from_dict(connexion.request.get_json())
    username = data.username
    password = data.password
    # 3. Kiểm tra thông tin đăng nhập
    if username == "admin" and password == "123456":
        # Tạo JWT token hợp lệ trong 30 phút
        token = jwt.encode(
            {
                "user": username,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=30)
            },
            SECRET_KEY,
            algorithm="HS256"
        )

        # Nếu token là bytes thì chuyển sang string
        if isinstance(token, bytes):
            token = token.decode("utf-8")

        # 4. Trả về token cho client
        return {"token": token}, 200

    # 5. Sai thông tin đăng nhập
    return {"message": "Invalid credentials"}, 401