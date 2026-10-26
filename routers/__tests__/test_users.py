from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core import exceptions
from google.cloud.firestore import SERVER_TIMESTAMP

from dependencies.firebase_auth import get_firebase_user_from_token

from ..users import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

mock_user = {
    "uid": "123",
    "email": "testuser@example.com"
}

async def override_firebase_user():
    return mock_user

@pytest.fixture
def mock_db():
    with patch("routers.users.db") as mock:
        yield mock

@pytest.fixture
def mock_document(mock_db):
    return mock_db.return_value.collection.return_value.document

@pytest.fixture(autouse=True)
def run_before_each_test():
    app.dependency_overrides[get_firebase_user_from_token] = override_firebase_user

    yield

    app.dependency_overrides.clear()

def test_me_with_mock_user():
    response = client.get("/users/me")
    assert response.status_code == 200
    assert response.json() == mock_user

def test_create_user(mock_db, mock_document):
    response = client.post("/users", json={"name": "testuser"})

    mock_db.return_value.collection.assert_called_once_with("users")
    mock_document.assert_called_once_with("123")
    mock_document.return_value.create.assert_called_once_with({
        "name": "testuser",
        "email": "testuser@example.com",
        "created_at": SERVER_TIMESTAMP
    })

    assert response.status_code == 201
    assert response.json() == { 'message': 'User 123 created!' }

def test_create_user_already_exists(mock_db, mock_document):
    mock_document.return_value.create.side_effect = exceptions.AlreadyExists("Already exists")

    response = client.post("/users", json={"name": "testuser"})

    mock_db.return_value.collection.assert_called_once_with("users")
    mock_document.assert_called_once_with("123")
    mock_document.return_value.create.assert_called_once_with({
        "name": "testuser",
        "email": "testuser@example.com",
        "created_at": SERVER_TIMESTAMP
    })

    assert response.status_code == 200
    assert response.json() == { 'message': 'User 123 already exists' }
