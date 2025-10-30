import connexion
from typing import Dict
from typing import Tuple
from typing import Union

from openapi_server.models.api_v1_login_post200_response import ApiV1LoginPost200Response  # noqa: E501
from openapi_server.models.api_v1_login_post_request import ApiV1LoginPostRequest  # noqa: E501
from openapi_server import util


def api_v1_login_post(body):  # noqa: E501
    """Login to obtain JWT token

     # noqa: E501

    :param api_v1_login_post_request: 
    :type api_v1_login_post_request: dict | bytes

    :rtype: Union[ApiV1LoginPost200Response, Tuple[ApiV1LoginPost200Response, int], Tuple[ApiV1LoginPost200Response, int, Dict[str, str]]
    """
    api_v1_login_post_request = body
    if connexion.request.is_json:
        api_v1_login_post_request = ApiV1LoginPostRequest.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
