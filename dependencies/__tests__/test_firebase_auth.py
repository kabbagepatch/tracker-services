from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from firebase_admin.auth import InvalidIdTokenError

from schemas.users import User

from ..firebase_auth import verify_user

mock_firebase_user = {
    "uid": "user123",
    "email": "testuser@example.com",
    "email_verified": True,
}
mock_user_data = User(
    uid="user123",
    name="Test User",
    email="testuser@example.com",
)

def mock_scope_get_secure(arg):
    if arg == "method": return "POST"
    if arg == "route": return MagicMock(path="/vinyls/")

def mock_scope_get_unverified(arg):
    if arg == "method": return "GET"
    if arg == "route": return MagicMock(path="/users/me")

def mock_scope_get_create_user(arg):
    if arg == "method": return "POST"
    if arg == "route": return MagicMock(path="/users/")

def mock_scope_get_verified(arg):
    if arg == "method": return "GET"
    if arg == "route": return MagicMock(path="/vinyls/{vinyl_id}")

def mock_scope_get_admin(arg):
    if arg == "method": return "DELETE"
    if arg == "route": return MagicMock(path="/users/{uid}")

@pytest.fixture
def mock_verify_id_token():
    with patch("dependencies.firebase_auth.verify_id_token", return_value=mock_firebase_user) as mock:
        yield mock

@pytest.fixture
def mock_token():
    mock_token = MagicMock()
    mock_token.credentials = "mock_token"
    return mock_token

@pytest.fixture
def mock_request():
    mock_request = MagicMock()
    mock_request.scope.get = mock_scope_get_unverified
    return mock_request

@pytest.fixture
def mock_get_user_data():
    with patch("dependencies.firebase_auth.get_user_data", return_value=mock_user_data) as mock:
        yield mock

def test_verify_user(mock_get_user_data, mock_verify_id_token, mock_token, mock_request):
    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": True,
        "is_guest": False,
        "user_data": mock_user_data.model_dump()
    }
    assert mock_request.state.uid == "user123"

    mock_verify_id_token.assert_called_once_with("mock_token", clock_skew_seconds=60, check_revoked=False)

def test_verify_user_secure_route(mock_get_user_data, mock_verify_id_token, mock_token, mock_request):
    mock_request.scope.get = mock_scope_get_secure

    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": True,
        "is_guest": False,
        "user_data": mock_user_data.model_dump()
    }
    assert mock_request.state.uid == "user123"

    mock_verify_id_token.assert_called_once_with("mock_token", clock_skew_seconds=60, check_revoked=True)

def test_verify_user_no_token(mock_verify_id_token):
    with pytest.raises(HTTPException) as exc_info:
        verify_user(request=MagicMock(), token=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid/Missing credentials"

def test_verify_user_invalid_token(mock_verify_id_token, mock_token):
    mock_verify_id_token.side_effect = InvalidIdTokenError("Invalid token")

    with pytest.raises(HTTPException) as exc_info:
        verify_user(request=MagicMock(), token=mock_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid/Missing credentials"

def test_verify_user_admin_route(mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_request.scope.get = mock_scope_get_admin
    mock_admin = User(
        uid="user123",
        name="Test User",
        email="testuser@example.com",
        admin=True
    )
    mock_get_user_data.return_value = mock_admin

    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": True,
        "is_guest": False,
        "user_data": mock_admin.model_dump()
    }

def test_verify_user_admin_route_no_data(mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_request.scope.get = mock_scope_get_admin
    mock_get_user_data.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        verify_user(request=mock_request, token=mock_token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "You do not have permission to access this resource"

def test_verify_user_admin_route_forbidden(mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_request.scope.get = mock_scope_get_admin

    with pytest.raises(HTTPException) as exc_info:
        verify_user(request=mock_request, token=mock_token)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "You do not have permission to access this resource"

def test_verify_user_unverified_email(mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_unverified = {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": False,
    }
    mock_verify_id_token.return_value = mock_unverified
        
    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": False,
        "is_guest": False,
        "user_data": mock_user_data.model_dump()
    }

def test_verify_user_guest_user(mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_unverified = {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": False,
        "firebase": { "sign_in_provider": "anonymous" }
    }
    mock_verify_id_token.return_value = mock_unverified
        
    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": False,
        "firebase": { "sign_in_provider": "anonymous" },
        "is_guest": True,
        "user_data": mock_user_data.model_dump()
    }

def test_verify_user_verified_route(mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_unverified = {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": False,
    }
    mock_verify_id_token.return_value = mock_unverified
    mock_request.scope.get = mock_scope_get_verified
        
    with pytest.raises(HTTPException) as exc_info:
            verify_user(request=mock_request, token=mock_token)
    
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Email not verified"

@patch("dependencies.firebase_auth.create_user")
def test_verify_user_create_user(mock_create_user, mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_get_user_data.return_value = None
        
    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": True,
        "is_guest": False,
        "user_data": None
    }

    mock_create_user.assert_called_once_with(uid='user123', email='testuser@example.com', is_guest=False)


@patch("dependencies.firebase_auth.create_user")
def test_verify_user_create_user_call(mock_create_user, mock_verify_id_token, mock_token, mock_get_user_data, mock_request):
    mock_get_user_data.return_value = None
    mock_request.scope.get = mock_scope_get_create_user

    result = verify_user(request=mock_request, token=mock_token)

    assert result == {
        "uid": "user123",
        "email": "testuser@example.com",
        "email_verified": True,
        "is_guest": False,
        "user_data": None
    }

    mock_create_user.assert_not_called()
