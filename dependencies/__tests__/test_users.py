from unittest.mock import patch

import pytest
from fastapi import HTTPException
from google.api_core import exceptions
from google.cloud.firestore import SERVER_TIMESTAMP

from schemas.users import User

from ..users import admin_check, create_user, get_user_data, set_discogs_requests

mock_user = {
    "uid": "user123",
    "name": "testuser",
    "email": "testuser@example.com",
    "vinyl_limit": 1000,
    "anonymous_discogs_requests_remaining": 20,
    "admin": False,
    "created_at": SERVER_TIMESTAMP
}

@pytest.fixture
def mock_db():
    with patch("dependencies.users.db") as mock:
        yield mock

@pytest.fixture
def mock_document(mock_db):
    return mock_db.return_value.collection.return_value.document

def test_create_user(mock_db, mock_document):
    result = create_user(uid="user123", name="testuser", email="testuser@example.com")

    mock_db.return_value.collection.assert_called_once_with("users")
    mock_document.assert_called_once_with("user123")
    mock_document.return_value.create.assert_called_once_with(mock_user)

    assert result is True

def test_create_user_guest(mock_db, mock_document):
    result = create_user(uid="user123", name="testuser", email="testuser@example.com", is_guest=True)

    mock_db.return_value.collection.assert_called_once_with("users")
    mock_document.assert_called_once_with("user123")
    mock_document.return_value.create.assert_called_once_with({
        **mock_user,
        "vinyl_limit": 10,
    })

    assert result is True

def test_create_user_already_exists(mock_db, mock_document):
    mock_document.return_value.create.side_effect = exceptions.AlreadyExists("Already exists")

    result = create_user(uid="user123", name="testuser", email="testuser@example.com")

    mock_db.return_value.collection.assert_called_once_with("users")
    mock_document.assert_called_once_with("user123")
    mock_document.return_value.create.assert_called_once_with(mock_user)

    assert result is False

def test_get_user_data(mock_document):
    mock_document.return_value.get.return_value.exists = True
    mock_document.return_value.get.return_value.to_dict.return_value = mock_user

    result = get_user_data("user123")

    assert result == User.model_validate(mock_user)

def test_get_user_data_not_found(mock_document):
    mock_document.return_value.get.return_value.exists = False

    result = get_user_data("user123")

    assert result is None

def test_set_discogs_requests(mock_document):
    mock_document.return_value.get.return_value.exists = True
    mock_document.return_value.get.return_value.to_dict.return_value = mock_user

    set_discogs_requests("user123", 13)

    mock_document.return_value.update.assert_called_once_with({
        "anonymous_discogs_requests_remaining": 13
    })

def test_admin_check_no_admin():
    with pytest.raises(HTTPException) as exc_info:
        admin_check({ "user_data": { "admin": False} })

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User is not an admin"

def test_admin_check_no_user():
    with pytest.raises(HTTPException) as exc_info:
        admin_check({})

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "User is not an admin"

def test_admin_check_admin():
    admin_check({ "user_data": { "admin": True} })
