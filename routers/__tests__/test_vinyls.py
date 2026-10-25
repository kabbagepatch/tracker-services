from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from google.api_core import exceptions
from google.cloud.firestore import SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_query import FieldFilter

from dependencies.firebase_auth import get_firebase_user_from_token
from schemas.vinyls import DiscogsAlbum, DiscogsRelease, Track, Vinyl, VinylPlay

from ..vinyls import VINYL_PLAYS, VINYLS, limiter, router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

mock_user = {
    "uid": "123",
    "email": "testuser@example.com"
}
mock_vinyl = Vinyl(
    album="Test Vinyl",
    artist="Test Artist",
    n_sides=4,
    discogs_release_id=999,
    discogs_master_id=555
)
mock_discogs_release = DiscogsRelease(
    id=999,
    master_id=555,
    album="Test Vinyl",
    artist="Test Artist",
    n_sides=4,
)
mock_vinyl_full = Vinyl(
    discogs_release_id=999,
    discogs_master_id=555,
    album="Test Vinyl",
    artist="Test Artist",
    n_sides=4,
    genres=["Pop", "Rock"],
    published=2019,
    image_url="http://example.com/album-image.jpg",
    release_image_url="http://example.com/release-image.jpg",
    album_image_url="http://example.com/album-image.jpg",
    tracks=[Track(
        position="A1",
        type_="track",
        title="Test Track",
        duration="3:45"
    )],
    disc_color_text="Orange marbled",
    favorite=False,
    deleted=False,
)
mock_discogs_release_full = DiscogsRelease(
    id=999,
    master_id=555,
    album="Test Vinyl",
    artist="Test Artist",
    n_sides=4,
    genres=["Pop", "Rock"],
    published=2025,
    image_url="http://example.com/release-image.jpg",
    tracks=[Track(
        position="A1",
        type_="track",
        title="Test Track",
        duration="3:45"
    )],
    disc_color_text="Orange marbled",
    barcode="1234567890",
)
mock_discogs_album = DiscogsAlbum(
    id=555,
    album="Test Vinyl",
    artist="Test Artist",
    published=2019,
    image_url="http://example.com/album-image.jpg",
)
mock_vinyl_play = VinylPlay(
    user_id="678",
    vinyl_id="123",
    sides=[1, 2, 3, 4],
    timestamp="2024-06-06T12:00:00Z"
)
mock_vinyl_play2 = VinylPlay(
    user_id="678",
    vinyl_id="123",
    sides=[1, 2],
    timestamp="2025-06-06T12:00:00Z"
)

async def override_firebase_user():
    return mock_user

def mock_snapshot(exists=True, data=None, id="123"):
    snapshot = MagicMock()
    snapshot.exists = exists
    snapshot.to_dict.return_value = data or {}
    snapshot.id = id
    snapshot.get.side_effect = lambda key, default=None: (data or {}).get(key, default)

    return snapshot

def mock_collection_fn(arg):
    collection = MagicMock()
    if arg == VINYL_PLAYS:
        collection.where.return_value.stream.return_value = [
            mock_snapshot(data=mock_vinyl_play.model_dump()),
            mock_snapshot(data=mock_vinyl_play2.model_dump()),
        ]
    if arg == VINYLS:
        collection.where.return_value.stream.return_value = [mock_snapshot(data=mock_vinyl.model_dump())]
    return collection

@pytest.fixture(autouse=True)
def run_before_each_test():
    limiter.enabled = False
    app.dependency_overrides[get_firebase_user_from_token] = override_firebase_user
    yield
    app.dependency_overrides.clear()

def test_without_credentials():
    app.dependency_overrides.clear()
    response = client.get("/vinyls")
    assert response.status_code == 401
    assert response.json() == { 'detail': 'Invalid/Missing credentials' }

@patch("routers.vinyls.get_discogs_album")
@patch("routers.vinyls.get_discogs_release")
@patch("routers.vinyls.db")
def test_create_vinyl_default(mock_db, mock_get_discogs_release, mock_get_discogs_album):
    mock_get_discogs_release.return_value = mock_discogs_release
    mock_get_discogs_album.return_value = None
    mock_collection = MagicMock()
    mock_document = MagicMock()
    mock_document.return_value.create.return_value = "Mocked Response"
    mock_collection.return_value.document = mock_document
    mock_db.return_value.collection = mock_collection
    
    response = client.post("/vinyls", json={"release_id": "999"})
    
    assert response.status_code == 201

    mock_collection.assert_called_once_with(VINYLS)
    mock_document.assert_called_once()
    mock_document.return_value.create.assert_called_once_with({
        **mock_vinyl.model_dump(),
        "user_id": "123",
        "created_at": SERVER_TIMESTAMP,
        "deleted": False
    })

@patch("routers.vinyls.get_discogs_album")
@patch("routers.vinyls.get_discogs_release")
@patch("routers.vinyls.db")
def test_create_vinyl_full(mock_db, mock_get_discogs_release, mock_get_discogs_album):
    mock_get_discogs_release.return_value = mock_discogs_release_full
    mock_get_discogs_album.return_value = mock_discogs_album
    mock_collection = MagicMock()
    mock_document = MagicMock()
    mock_document.return_value.create.return_value = "Mocked Response"
    mock_collection.return_value.document = mock_document
    mock_db.return_value.collection = mock_collection
    
    response = client.post("/vinyls", json={"release_id": "999"})
    
    assert response.status_code == 201

    mock_collection.assert_called_once_with(VINYLS)
    mock_document.assert_called_once()
    mock_document.return_value.create.assert_called_once_with({
        **mock_vinyl_full.model_dump(),
        "user_id": "123",
        "created_at": SERVER_TIMESTAMP,
        "deleted": False
    })

@patch("routers.vinyls.db")
def test_create_vinyl_no_discogs_id(mock_db):
    mock_collection = MagicMock()
    mock_db.return_value.collection.return_value = mock_collection
    
    response = client.post("/vinyls", json={"album": "New Vinyl"})
    
    assert response.status_code == 400
    assert response.json() == { 'message': 'release_id is required. Custom vinyls not supported at the moment' }

    mock_collection.assert_not_called();

@patch("routers.vinyls.get_discogs_release")
@patch("routers.vinyls.db")
def test_create_vinyl_no_discogs_release(mock_db, mock_get_discogs_release):
    mock_get_discogs_release.return_value = None
    mock_collection = MagicMock()
    mock_db.return_value.collection.return_value = mock_collection
    
    response = client.post("/vinyls", json={"release_id": "999"})
    
    assert response.status_code == 400
    assert response.json() == { 'message': 'Invalid release_id. No release found' }

    mock_collection.assert_not_called();

@patch("routers.vinyls.db")
def test_list_vinyls(mock_db):
    mock_db.return_value.collection.return_value.where.return_value.where.return_value.stream.return_value = [mock_snapshot(data=mock_vinyl.model_dump())]

    response = client.get("/vinyls")

    mock_db.return_value.collection.assert_called_once_with(VINYLS)
    assert response.status_code == 200
    assert response.json() == [mock_vinyl.model_dump() | {"id": "123"}]

@patch("routers.vinyls.db")
def test_list_vinyl_plays(mock_db):
    mock_db.return_value.collection.side_effect = mock_collection_fn

    response = client.get("/vinyls/activity")

    mock_db.assert_has_calls([call(), call().collection(VINYL_PLAYS), call(), call().collection(VINYLS)])
    assert response.status_code == 200
    assert response.json() == [{
        'album': 'Test Vinyl',
        'artist': 'Test Artist',
        'n_sides': 4,
        'image_url': '',
        'album_colors': [],
        'deleted': False,
        'play_id': '123',
        'vinyl_id': '123',
        'sides': [1, 2],
        'timestamp': '2025-06-06T12:00:00Z',
    },{
        'album': 'Test Vinyl',
        'artist': 'Test Artist',
        'n_sides': 4,
        'image_url': '',
        'album_colors': [],
        'deleted': False,
        'play_id': '123',
        'vinyl_id': '123',
        'sides': [1, 2, 3, 4],
        'timestamp': '2024-06-06T12:00:00Z',
    }]

# def test_create_user_already_exists():
#     with patch("routers.users.db") as mock_db:
#         mock_db.return_value.collection.return_value.document.return_value.create.side_effect = exceptions.AlreadyExists("Already exists")
        
#         response = client.post("/users", json={"name": "testuser"})

#         mock_db.return_value.collection.assert_called_once_with("users")
#         mock_db.return_value.collection.return_value.document.assert_called_once_with("123")
#         mock_db.return_value.collection.return_value.document.return_value.create.assert_called_once_with({
#             "name": "testuser",
#             "email": "testuser@example.com",
#             "created_at": SERVER_TIMESTAMP
#         })
        
#         assert response.status_code == 200
#         assert response.json() == { 'message': 'User 123 already exists' }
