import connexion
from typing import Dict
from typing import Tuple
from typing import Union

from openapi_server.models.api_v1_books_borrowed_get200_response import ApiV1BooksBorrowedGet200Response  # noqa: E501
from openapi_server.models.book_borrowed import BookBorrowed  # noqa: E501
from openapi_server.models.new_book_borrowed import NewBookBorrowed  # noqa: E501
from openapi_server import util


def api_v1_books_borrowed_get(member_id=None, cursor=None, limit=None):  # noqa: E501
    """Get list of borrowed books (cursor-based pagination)

     # noqa: E501

    :param member_id: Filter by member ID
    :type member_id: int
    :param cursor: Cursor indicating the last retrieved borrow record ID
    :type cursor: int
    :param limit: Number of records to retrieve
    :type limit: int

    :rtype: Union[ApiV1BooksBorrowedGet200Response, Tuple[ApiV1BooksBorrowedGet200Response, int], Tuple[ApiV1BooksBorrowedGet200Response, int, Dict[str, str]]
    """
    return 'do some magic!'


def api_v1_books_borrowed_post(body):  # noqa: E501
    """Create a new book borrowing record

     # noqa: E501

    :param new_book_borrowed: 
    :type new_book_borrowed: dict | bytes

    :rtype: Union[BookBorrowed, Tuple[BookBorrowed, int], Tuple[BookBorrowed, int, Dict[str, str]]
    """
    new_book_borrowed = body
    if connexion.request.is_json:
        new_book_borrowed = NewBookBorrowed.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
