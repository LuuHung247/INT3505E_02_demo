import unittest

from flask import json

from openapi_server.models.api_v1_books_borrowed_get200_response import ApiV1BooksBorrowedGet200Response  # noqa: E501
from openapi_server.models.book_borrowed import BookBorrowed  # noqa: E501
from openapi_server.models.new_book_borrowed import NewBookBorrowed  # noqa: E501
from openapi_server.test import BaseTestCase


class TestBooksBorrowedController(BaseTestCase):
    """BooksBorrowedController integration test stubs"""

    def test_api_v1_books_borrowed_get(self):
        """Test case for api_v1_books_borrowed_get

        Get list of borrowed books (cursor-based pagination)
        """
        query_string = [('member_id', 56),
                        ('cursor', 56),
                        ('limit', 10)]
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books-borrowed',
            method='GET',
            headers=headers,
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_books_borrowed_post(self):
        """Test case for api_v1_books_borrowed_post

        Create a new book borrowing record
        """
        new_book_borrowed = {"member_id":1,"book_id":2}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books-borrowed',
            method='POST',
            headers=headers,
            data=json.dumps(new_book_borrowed),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
