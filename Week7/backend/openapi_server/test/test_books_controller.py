import unittest

from flask import json

from openapi_server.models.api_v1_books_get200_response import ApiV1BooksGet200Response  # noqa: E501
from openapi_server.models.book import Book  # noqa: E501
from openapi_server.models.new_book import NewBook  # noqa: E501
from openapi_server.models.update_book import UpdateBook  # noqa: E501
from openapi_server.test import BaseTestCase


class TestBooksController(BaseTestCase):
    """BooksController integration test stubs"""

    def test_api_v1_books_book_id_delete(self):
        """Test case for api_v1_books_book_id_delete

        Delete a book
        """
        headers = { 
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books/{book_id}'.format(book_id=56),
            method='DELETE',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_books_book_id_get(self):
        """Test case for api_v1_books_book_id_get

        Get a book by ID
        """
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books/{book_id}'.format(book_id=56),
            method='GET',
            headers=headers)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_books_book_id_put(self):
        """Test case for api_v1_books_book_id_put

        Update a book or handle borrow/return logic
        """
        update_book = {"author":"Updated Author","available":False,"title":"Updated Title"}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books/{book_id}'.format(book_id=56),
            method='PUT',
            headers=headers,
            data=json.dumps(update_book),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_books_get(self):
        """Test case for api_v1_books_get

        Get all books with optional filters (cursor-based pagination)
        """
        query_string = [('available', True),
                        ('title', 'title_example'),
                        ('author', 'author_example'),
                        ('cursor', 56),
                        ('limit', 10)]
        headers = { 
            'Accept': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books',
            method='GET',
            headers=headers,
            query_string=query_string)
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))

    def test_api_v1_books_post(self):
        """Test case for api_v1_books_post

        Create a new book
        """
        new_book = {"author":"James Clear","title":"Atomic Habits"}
        headers = { 
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': 'Bearer special-key',
        }
        response = self.client.open(
            '/api/v1/books',
            method='POST',
            headers=headers,
            data=json.dumps(new_book),
            content_type='application/json')
        self.assert200(response,
                       'Response body is : ' + response.data.decode('utf-8'))


if __name__ == '__main__':
    unittest.main()
