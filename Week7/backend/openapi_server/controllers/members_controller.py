import connexion
from typing import Dict
from typing import Tuple
from typing import Union

from openapi_server.models.api_v1_members_get200_response import ApiV1MembersGet200Response  # noqa: E501
from openapi_server.models.member import Member  # noqa: E501
from openapi_server.models.new_member import NewMember  # noqa: E501
from openapi_server import util


def api_v1_members_get(name=None, cursor=None, limit=None):  # noqa: E501
    """Get all members with optional filter (cursor-based pagination)

     # noqa: E501

    :param name: Filter by member name
    :type name: str
    :param cursor: Cursor indicating the last retrieved member ID
    :type cursor: int
    :param limit: Number of members to retrieve
    :type limit: int

    :rtype: Union[ApiV1MembersGet200Response, Tuple[ApiV1MembersGet200Response, int], Tuple[ApiV1MembersGet200Response, int, Dict[str, str]]
    """
    return 'do some magic!'


def api_v1_members_post(body):  # noqa: E501
    """Create a new member

     # noqa: E501

    :param new_member: 
    :type new_member: dict | bytes

    :rtype: Union[Member, Tuple[Member, int], Tuple[Member, int, Dict[str, str]]
    """
    new_member = body
    if connexion.request.is_json:
        new_member = NewMember.from_dict(connexion.request.get_json())  # noqa: E501
    return 'do some magic!'
