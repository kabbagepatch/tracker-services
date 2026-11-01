from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from firebase_admin.exceptions import FirebaseError

from dependencies.firebase_auth import verify_user
from schemas.users import User

from ..users import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

mock_user = {
    "uid": "123",
    "name": "Test User",
    "email": "testuser@example.com",
    "user_data": { "uid": "123", "name": "Test User", "email": "testuser@example.com" }
}

async def override_firebase_user():
    return mock_user

@pytest.fixture
def mock_db():
    with patch("routers.users.db") as mock:
        yield mock

@pytest.fixture
def mock_collection(mock_db):
    return mock_db.return_value.collection

@pytest.fixture
def mock_document(mock_collection):
    return mock_collection.return_value.document

@pytest.fixture
def mock_admin_check():
    with patch("routers.users.admin_check") as mock:
        yield mock

@pytest.fixture(autouse=True)
def run_before_each_test():
    app.dependency_overrides[verify_user] = override_firebase_user

    yield

    app.dependency_overrides.clear()

@patch("routers.users.create_user")
def test_sign_up(mock_create_user):
    mock_create_user.return_value = True

    response = client.post("/users", json={"name": "testuser"})

    assert response.status_code == 201
    assert response.json() == { 'message': 'User 123 created!' }
    mock_create_user.assert_called_once_with(uid='123', name='testuser', email='testuser@example.com', is_guest=False)

@patch("routers.users.create_user")
def test_sign_up_guest(mock_create_user):
    app.dependency_overrides[verify_user] = lambda: { "uid": "123", "name": "Test User", "email": "testuser@example.com", "is_guest": True }
    mock_create_user.return_value = True

    response = client.post("/users", json={"name": "testuser"})

    assert response.status_code == 201
    assert response.json() == { 'message': 'User 123 created!' }
    mock_create_user.assert_called_once_with(uid='123', name='testuser', email='testuser@example.com', is_guest=True)

@patch("routers.users.create_user")
def test_sign_up_already_exists(mock_create_user):
    mock_create_user.return_value = False

    response = client.post("/users", json={"name": "testuser"})

    assert response.status_code == 200
    assert response.json() == { 'message': 'User 123 already exists' }
    mock_create_user.assert_called_once_with(uid='123', name='testuser', email='testuser@example.com', is_guest=False)

def test_list_users(mock_collection, mock_admin_check):
    mock_collection.return_value.stream.return_value = [
        MagicMock(id="123", to_dict=lambda: {"name": "Test User", "email": "testuser@example.com"}),
        MagicMock(id="456", to_dict=lambda: {"name": "Another User", "email": "anotheruser@example.com"})
    ]

    response = client.get("/users")

    assert mock_admin_check.called
    assert response.status_code == 200
    assert response.json() == [
        {
            "uid": "123",
            "name": "Test User",
            "email": "testuser@example.com",
            "vinyl_limit": 1000,
            "anonymous_discogs_requests_remaining": 20,
            "admin": False
        },
        {
            "uid": "456",
            "name": "Another User",
            "email": "anotheruser@example.com",
            "vinyl_limit": 1000,
            "anonymous_discogs_requests_remaining": 20,
            "admin": False
        }
    ]

def test_me():
    response = client.get("/users/me")
    
    assert response.status_code == 200
    assert response.json() == {
        "name": "Test User",
        "email": "testuser@example.com",
        "vinyl_limit": 1000,
        "anonymous_discogs_requests_remaining": 20,
    }

def test_me_not_found():
    app.dependency_overrides[verify_user] = lambda: { "uid": "123", "email": "testuser@example.com" }
    
    response = client.get("/users/me")
    
    assert response.status_code == 404
    assert response.json() == { "detail": "User not found" }

def test_update_user(mock_collection, mock_document):
    response = client.put("/users/me", json={"name": "Updated User"})

    assert response.status_code == 200

    mock_collection.assert_called_once_with("users")
    mock_document.return_value.update.assert_called_once_with({
        "uid": "123",
        "name": "Updated User",
        "email": "testuser@example.com",
        "vinyl_limit": 1000,
        "anonymous_discogs_requests_remaining": 20,
        "admin": False,
    })

def test_update_user_no_email(mock_document):
    app.dependency_overrides[verify_user] = lambda: { "uid": "123" }

    response = client.put("/users/me", json={"name": "Updated User"})

    assert response.status_code == 400
    assert response.json() == { "detail": "Email is required for updating user profile" }

@patch("routers.users.get_user_data")
def test_get_user(mock_get_user_data, mock_admin_check):
    mock_get_user_data.return_value = User(
        uid="user123",
        name="Test User",
        email="testuser@example.com"
    )

    response = client.get("/users/user123")

    assert mock_admin_check.called
    assert response.status_code == 200
    assert response.json() == {
        "name": "Test User",
        "email": "testuser@example.com",
        "vinyl_limit": 1000,
        "anonymous_discogs_requests_remaining": 20.
    }

@patch("routers.users.get_user_data")
def test_get_user_not_found(mock_get_user_data, mock_admin_check):
    mock_get_user_data.return_value = None

    response = client.get("/users/user123")

    assert mock_admin_check.called
    assert response.status_code == 404
    assert response.json() == { "detail": "User not found" }

@patch("routers.users.auth")
def test_delete_user(mock_auth, mock_db, mock_collection, mock_admin_check):
    mock_collection.return_value.where.return_value.stream.return_value = [
        MagicMock(), MagicMock(),
    ]
    response = client.delete("/users/user123")

    assert mock_admin_check.called
    assert response.status_code == 204
    assert mock_db.return_value.batch.return_value.delete.call_count == 5
    mock_auth.delete_user.assert_called_once_with("user123")

def test_delete_user_same_user(mock_db):
    response = client.delete("/users/123")

    assert response.status_code == 400
    assert response.json() == { "detail": "Cannot delete your own account" }
    assert mock_db.call_count == 0


@patch("routers.users.auth")
def test_delete_user_firebase_error(mock_auth, mock_db, mock_collection, mock_admin_check):
    mock_auth.delete_user.side_effect = FirebaseError(400, "")
    response = client.delete("/users/user123")

    assert mock_admin_check.called
    assert response.status_code == 500
    assert response.json() == { "detail": "Failed to delete user from authentication. Database deletion may have occurred." }
    mock_auth.delete_user.assert_called_once_with("user123")
