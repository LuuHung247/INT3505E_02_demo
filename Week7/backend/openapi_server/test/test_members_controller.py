import unittest

from flask import json

from openapi_server.models.api_v1_members_get200_response import ApiV1MembersGet200Response  # noqa: E501
from openapi_server.models.member import Member  # noqa: E501
from openapi_server.models.new_member import NewMember  # noqa: E501
from openapi_server.test import BaseTestCase


class TestMembersController(BaseTestCase):
    """MembersController integration test stubs"""

    def test_api_v1_members_get(self):
        """Test case for api_v1_members_get

        Get all members with optional filter (cursor-based pagination)
        """
        query_string = [('name', 'name_example'),
                        ('cursor', 56),
                        ('limit', 10)]
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/members',
            method='GET',
            headers=headers,
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_members_post(self):
        """Test case for api_v1_members_post

        Create a new member
        """
        new_member = {"name":"Jane Doe","email":"jane@example.com"}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/members',
            method='POST',
            headers=headers,
            data=json.dumps(new_member),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
