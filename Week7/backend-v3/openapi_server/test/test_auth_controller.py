import unittest

from flask import json

from openapi_server.models.api_v1_login_post200_response import ApiV1LoginPost200Response  # noqa: E501
from openapi_server.models.api_v1_login_post_request import ApiV1LoginPostRequest  # noqa: E501
from openapi_server.test import BaseTestCase


class TestAuthController(BaseTestCase):
    """AuthController integration test stubs"""

    def test_api_v1_login_post(self):
        """Test case for api_v1_login_post

        Login to obtain JWT token
        """
        api_v1_login_post_request = openapi_server.ApiV1LoginPostRequest()
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/login',
            method='POST',
            headers=headers,
            data=json.dumps(api_v1_login_post_request),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
