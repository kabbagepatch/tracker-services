from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from firebase_admin.auth import InvalidIdTokenError

from ..firebase_auth import get_firebase_user_from_token


@pytest.fixture
def mock_verify_id_token():
    with patch("dependencies.firebase_auth.verify_id_token") as mock:
        yield mock

def test_get_firebase_user(mock_verify_id_token):
    mock_request = MagicMock()
    mock_token = MagicMock()
    mock_token.credentials = "mock_token"
    mock_verify_id_token.return_value = {"uid": "user123", "email": "testuser@example.com"}

    result = get_firebase_user_from_token(request=mock_request, token=mock_token) # type: ignore

    assert result == {"uid": "user123", "email": "testuser@example.com"}
    assert mock_request.state.uid == "user123"

def test_get_firebase_user_no_token(mock_verify_id_token):
    mock_request = MagicMock()
    mock_verify_id_token.return_value = {"uid": "user123", "email": "testuser@example.com"}

    with pytest.raises(HTTPException) as exc_info:
        get_firebase_user_from_token(request=mock_request, token=None) # type: ignore

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid/Missing credentials"

def test_get_firebase_user_invalid_token(mock_verify_id_token):
    mock_request = MagicMock()
    mock_token = MagicMock()
    mock_token.credentials = "mock_token"
    mock_verify_id_token.side_effect = InvalidIdTokenError("Invalid token")

    with pytest.raises(HTTPException) as exc_info:
        get_firebase_user_from_token(request=mock_request, token=mock_token) # type: ignore

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid/Missing credentials"
