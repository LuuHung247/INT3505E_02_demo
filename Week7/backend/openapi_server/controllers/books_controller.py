import connexion
from typing import Dict
from typing import Tuple
from typing import Union

from openapi_server.models.api_v1_books_get200_response import ApiV1BooksGet200Response  # noqa: E501
from openapi_server.models.book import Book  # noqa: E501
from openapi_server.models.new_book import NewBook  # noqa: E501
from openapi_server.models.update_book import UpdateBook  # noqa: E501
from openapi_server import util


def api_v1_books_book_id_delete(book_id):  # noqa: E501
    """Delete a book

     # noqa: E501

    :param book_id: 
    :type book_id: int

    :rtype: Union[None, Tuple[None, int], Tuple[None, int, Dict[str, str]]
    """
    return 'do some magic!'


def api_v1_books_book_id_get(book_id):  # noqa: E501
    """Get a book by ID

     # noqa: E501

    :param book_id: 
    :type book_id: int

    :rtype: Union[Book, Tuple[Book, int], Tuple[Book, int, Dict[str, str]]
    """
    return 'do some magic!'


def api_v1_books_book_id_put(book_id, body):  # noqa: E501
    """Update a book or handle borrow/return logic

     # noqa: E501

    :param book_id: 
    :type book_id: int
    :param update_book: 
    :type update_book: dict | bytes

    :rtype: Union[Book, Tuple[Book, int], Tuple[Book, int, Dict[str, str]]
    """
    update_book = body
    if connexion.request.is_json:
        update_book = UpdateBook.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'


def api_v1_books_get(available=None, title=None, author=None, cursor=None, limit=None):  # noqa: E501
    """Get all books with optional filters (cursor-based pagination)

     # noqa: E501

    :param available: Filter books by availability
    :type available: bool
    :param title: Filter books by title
    :type title: str
    :param author: Filter books by author
    :type author: str
    :param cursor: Cursor indicating the last retrieved book ID
    :type cursor: int
    :param limit: Number of books to retrieve per request
    :type limit: int

    :rtype: Union[ApiV1BooksGet200Response, Tuple[ApiV1BooksGet200Response, int], Tuple[ApiV1BooksGet200Response, int, Dict[str, str]]
    """
    return 'do some magic!'


def api_v1_books_post(body):  # noqa: E501
    """Create a new book

     # noqa: E501

    :param new_book: 
    :type new_book: dict | bytes

    :rtype: Union[Book, Tuple[Book, int], Tuple[Book, int, Dict[str, str]]
    """
    new_book = body
    if connexion.request.is_json:
        new_book = NewBook.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
