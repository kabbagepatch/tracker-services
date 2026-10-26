from datetime import datetime
from unittest.mock import MagicMock, call, patch

import pytest
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from google.cloud.firestore import SERVER_TIMESTAMP

from dependencies.firebase_auth import get_firebase_user_from_token
from schemas.vinyls import DiscogsAlbum, DiscogsRelease, Track, Vinyl, VinylPlay

from ..vinyls import VINYL_PLAYS, VINYLS, get_owned_vinyl, limiter, router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

mock_user = {
    "uid": "user678",
    "email": "testuser@example.com"
}
mock_vinyl = Vinyl(
    user_id="user678",
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
    user_id="user678",
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
    album_colors=['#14521a', '#51faa2'],
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
    user_id="user678",
    vinyl_id="123",
    sides=[1, 2, 3, 4],
    timestamp="2024-06-06T12:00:00Z"
)
mock_vinyl_play2 = VinylPlay(
    user_id="user678",
    vinyl_id="123",
    sides=[1, 2],
    timestamp="2025-06-06T12:00:00Z"
)
mock_vinyl_play3 = VinylPlay(
    user_id="user678",
    vinyl_id="bad",
    sides=[1, 2],
    timestamp="2025-06-06T12:00:00Z"
)

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
            mock_snapshot(data=mock_vinyl_play3.model_dump()),
        ]
    if arg == VINYLS:
        collection.where.return_value.stream.return_value = [mock_snapshot(data=mock_vinyl.model_dump())]
    return collection

@pytest.fixture(autouse=True)
def run_before_each_test():
    limiter.enabled = False
    app.dependency_overrides[get_firebase_user_from_token] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    limiter.enabled = True

@pytest.fixture
def mock_db():
    with patch("routers.vinyls.db") as mock:
        yield mock

@pytest.fixture
def mock_collection(mock_db):
    return mock_db.return_value.collection

@pytest.fixture
def mock_document(mock_collection):
    return mock_collection.return_value.document

@pytest.fixture
def mock_vinyl_ref():
    return MagicMock()

@pytest.fixture
def mock_get_owned_vinyl(mock_vinyl_ref):
    with patch("routers.vinyls.get_owned_vinyl", return_value=(mock_vinyl, mock_vinyl_ref)) as mock:
        yield mock

@pytest.fixture
def mock_Client():
    with patch("dependencies.image_colors.httpx.Client") as mock:
        yield mock

@pytest.fixture
def mock_client(mock_Client):
    return mock_Client.return_value.__enter__.return_value

@patch("routers.vinyls.get_discogs_release")
def test_get_release(mock_get_discogs_release):
    mock_get_discogs_release.return_value = mock_discogs_release

    response = client.get("/vinyls/release/999")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_discogs_release.model_dump()

@patch("routers.vinyls.get_discogs_album")
def test_get_album(mock_get_discogs_album):
    mock_get_discogs_album.return_value = mock_discogs_album

    response = client.get("/vinyls/album/999")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_discogs_album.model_dump()

@patch("routers.vinyls.get_settings")
def test_search_discogs_release(mock_get_settings, mock_Client, mock_client):
    mock_vinyl_result = {
        "id": 999,
        "master_id": 999,
        "title": "Carly Rae Jepsen",
        "year": 2015,
        "genre": ["Pop"],
        "cover_image": "http://example.com/image.jpg",
        "formats": [{"text": "Black"}],
        "barcode": ["1234567890123"]
    }
    mock_client.get.return_value.json.return_value = {
        "results": [mock_vinyl_result]
    }

    response = client.get("/vinyls/search?term=Carly")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [{
        "release_id": 999,
        "master_id": 999,
        "title": "Carly Rae Jepsen",
        "published": 2015,
        "genres": ["Pop"],
        "image_url": "http://example.com/image.jpg",
        "disc_color_text": "Black",
        "barcode": "1234567890123"
    }]

@patch("routers.vinyls.get_settings")
def test_search_discogs_release_empty(mock_get_settings, mock_Client, mock_client):
    response = client.get("/vinyls/search?term=Carly")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []

@patch("routers.vinyls.get_discogs_album")
def test_search_discogs_release_no_term(mock_get_discogs_album):
    mock_get_discogs_album.return_value = mock_discogs_album

    response = client.get("/vinyls/search")
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"message": "Search term of at least length 3 is required"}

@patch("routers.vinyls.get_discogs_album")
def test_search_discogs_release_short_term(mock_get_discogs_album):
    mock_get_discogs_album.return_value = mock_discogs_album

    response = client.get("/vinyls/search?term=ab")
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"message": "Search term of at least length 3 is required"}

@patch("routers.vinyls.get_top_colors")
@patch("routers.vinyls.get_discogs_album")
@patch("routers.vinyls.get_discogs_release")
def test_create_vinyl_default(mock_get_discogs_release, mock_get_discogs_album, mock_get_top_colors, mock_collection, mock_document):
    mock_get_discogs_release.return_value = mock_discogs_release
    mock_get_discogs_album.return_value = None
    mock_get_top_colors.return_value = []

    response = client.post("/vinyls", json={"release_id": "999"})
    
    assert response.status_code == status.HTTP_201_CREATED
    mock_collection.assert_called_once_with(VINYLS)
    mock_document.assert_called_once()
    mock_document.return_value.create.assert_called_once_with({
        **mock_vinyl.model_dump(),
        "created_at": SERVER_TIMESTAMP,
    })

@patch("routers.vinyls.get_top_colors")
@patch("routers.vinyls.get_discogs_album")
@patch("routers.vinyls.get_discogs_release")
def test_create_vinyl_full(mock_get_discogs_release, mock_get_discogs_album, mock_get_top_colors, mock_collection, mock_document):
    mock_get_discogs_release.return_value = mock_discogs_release_full
    mock_get_discogs_album.return_value = mock_discogs_album
    mock_get_top_colors.return_value = ['#14521a', '#51faa2']

    response = client.post("/vinyls", json={"release_id": "999"})
    
    assert response.status_code == status.HTTP_201_CREATED
    mock_collection.assert_called_once_with(VINYLS)
    mock_document.assert_called_once()
    mock_document.return_value.create.assert_called_once_with({
        **mock_vinyl_full.model_dump(),
        "created_at": SERVER_TIMESTAMP,
    })

def test_create_vinyl_no_discogs_id(mock_collection):
    response = client.post("/vinyls", json={"album": "New Vinyl"})
    
    assert response.status_code == 400
    assert response.json() == { 'message': 'release_id is required. Custom vinyls not supported at the moment' }
    mock_collection.assert_not_called()

@patch("routers.vinyls.get_discogs_release")
def test_create_vinyl_no_discogs_release(mock_get_discogs_release, mock_collection):
    mock_get_discogs_release.return_value = None

    response = client.post("/vinyls", json={"release_id": "999"})

    assert response.status_code == 400
    assert response.json() == { 'message': 'Invalid release_id. No release found' }
    mock_collection.assert_not_called()

def test_list_vinyls(mock_collection):
    mock_collection.return_value.where.return_value.where.return_value.stream.return_value = [mock_snapshot(data=mock_vinyl.model_dump())]

    response = client.get("/vinyls")

    mock_collection.assert_called_once_with(VINYLS)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [mock_vinyl.model_dump() | {"id": "123"}]

def test_list_vinyl_plays_empty(mock_collection):
    mock_collection.return_value.where.return_value.stream.return_value = []

    response = client.get("/vinyls/activity")

    mock_collection.assert_called_once_with(VINYL_PLAYS)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []

def test_list_vinyl_plays(mock_db, mock_collection):
    mock_collection.side_effect = mock_collection_fn

    response = client.get("/vinyls/activity")

    mock_db.assert_has_calls([call(), call().collection(VINYL_PLAYS), call(), call().collection(VINYLS)])
    assert response.status_code == status.HTTP_200_OK
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

def test_get_owned_vinyl(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(data=mock_vinyl.model_dump())

    response = get_owned_vinyl("user678", "123")
    assert response[0] == mock_vinyl
    assert response[1] == mock_document.return_value

def test_get_owned_vinyl_user_mismatch(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(data=mock_vinyl.model_dump())

    with pytest.raises(HTTPException) as exc_info:
        get_owned_vinyl("user999", "123")
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "You do not have access to this vinyl"

def test_get_owned_vinyl_deleted(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(data={**mock_vinyl.model_dump(), "deleted": True})

    with pytest.raises(HTTPException) as exc_info:
        get_owned_vinyl("user678", "123")
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.detail == "This vinyl has been deleted"

def test_get_owned_vinyl_not_found(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(exists=False)

    with pytest.raises(HTTPException) as exc_info:
        get_owned_vinyl("user678", "123")
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.detail == "No vinyl found by that id"

def test_get_vinyl(mock_get_owned_vinyl):
    response = client.get("/vinyls/123")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_vinyl.model_dump()

def test_update_vinyl(mock_get_owned_vinyl, mock_vinyl_ref):
    updates = {
        "album": "Updated Title",
        "artist": "Updated Artist",
    }
    response = client.put("/vinyls/123", json=updates)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_vinyl.model_dump() | updates
    mock_vinyl_ref.update.assert_called_once_with(updates)

def test_update_vinyl_bad_disc_color(mock_get_owned_vinyl, mock_vinyl_ref):
    updates = {
        "disc_color_hex": "red",
    }
    response = client.put("/vinyls/123", json=updates)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    mock_vinyl_ref.update.assert_not_called()

def test_update_vinyl_favorite(mock_get_owned_vinyl, mock_vinyl_ref):
    updates = {
        "favorite": True,
    }
    response = client.put("/vinyls/123/favorite", json=updates)
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_vinyl.model_dump() | updates
    mock_vinyl_ref.update.assert_called_once_with(updates)

def test_delete_vinyl(mock_get_owned_vinyl, mock_vinyl_ref):
    response = client.delete("/vinyls/123")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""
    mock_vinyl_ref.update.assert_called_once_with({ "deleted": True })

def test_create_vinyl_play_default(mock_get_owned_vinyl, mock_collection, mock_document):
    mock_play_data = {
        "user_id": "user678",
        "vinyl_id": "123",
        "sides": [1,2,3,4],
        "timestamp": SERVER_TIMESTAMP,
    }

    response = client.post("/vinyls/123/plays", json={})

    assert response.status_code == status.HTTP_201_CREATED
    mock_collection.assert_called_once_with(VINYL_PLAYS)
    mock_document.assert_called_once()
    mock_document.return_value.create.assert_called_once_with(mock_play_data)

def test_create_vinyl_play_with_data(mock_get_owned_vinyl, mock_collection, mock_document):
    mock_play_data = {
        "user_id": "user678",
        "vinyl_id": "123",
        "sides": [1,2],
        "timestamp": datetime.fromisoformat("2025-06-05T14:48:00.000Z"),
    }
    mock_document.return_value.get.return_value.to_dict.return_value = mock_play_data
    mock_document.return_value.id = "play111"

    response = client.post("/vinyls/123/plays", json={ "sides": [1,2], "timestamp": "2025-06-05T14:48:00.000Z" })

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json() == {
        "user_id": "user678",
        "vinyl_id": "123",
        "sides": [1,2],
        "timestamp": "2025-06-05T14:48:00+00:00",
        "play_id": "play111",
        "album": mock_vinyl.album,
        "artist": mock_vinyl.artist,
        "image_url": mock_vinyl.image_url,
        "n_sides": mock_vinyl.n_sides,
        "album_colors": mock_vinyl.album_colors
    }
    mock_collection.assert_called_once_with(VINYL_PLAYS)
    mock_document.assert_called_once()
    mock_document.return_value.create.assert_called_once_with(mock_play_data)

def test_get_vinyl_plays(mock_get_owned_vinyl, mock_collection):
    mock_where = mock_collection.return_value.where
    mock_where.return_value.where.return_value.stream.return_value = [
        mock_snapshot(data=mock_vinyl_play.model_dump(), id="play1"),
        mock_snapshot(data=mock_vinyl_play2.model_dump(), id="play2"),
    ]

    response = client.get("/vinyls/123/plays")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "album": mock_vinyl.album,
        "artist": mock_vinyl.artist,
        "n_sides": mock_vinyl.n_sides,
        "image_url": mock_vinyl.image_url,
        "plays": [{
            "play_id": "play1",
            "sides": [1, 2, 3, 4],
            "timestamp": "2024-06-06T12:00:00Z",
        }, {
            "play_id": "play2",
            "sides": [1, 2],
            "timestamp": "2025-06-06T12:00:00Z",
        }]
    }
    mock_get_owned_vinyl.assert_called_once_with("user678", "123")
    mock_collection.assert_called_once_with(VINYL_PLAYS)
    user_filter = mock_where.call_args.kwargs["filter"]
    vinyl_filter = mock_where.return_value.where.call_args.kwargs["filter"]
    assert (user_filter.field_path, user_filter.op_string, user_filter.value) == ("user_id", "==", "user678")
    assert (vinyl_filter.field_path, vinyl_filter.op_string, vinyl_filter.value) == ("vinyl_id", "==", "123")

def test_get_vinyl_plays_empty(mock_get_owned_vinyl, mock_collection):
    mock_collection.return_value.where.return_value.where.return_value.stream.return_value = []

    response = client.get("/vinyls/123/plays")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["plays"] == []

def test_delete_play(mock_collection, mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(data=mock_vinyl_play.model_dump(), id="play1")

    response = client.delete("/vinyls/123/plays/play1")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert response.content == b""
    mock_collection.assert_called_once_with(VINYL_PLAYS)
    mock_document.assert_called_once_with("play1")
    mock_document.return_value.delete.assert_called_once()

def test_delete_play_not_found(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(exists=False)

    response = client.delete("/vinyls/123/plays/play1")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    mock_document.return_value.delete.assert_not_called()

def test_delete_play_user_mismatch(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(data={**mock_vinyl_play.model_dump(), "user_id": "user999"})

    response = client.delete("/vinyls/123/plays/play1")

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == { "detail": "You do not have access to this vinyl" }
    mock_document.return_value.delete.assert_not_called()

def test_delete_play_vinyl_mismatch(mock_document):
    mock_document.return_value.get.return_value = mock_snapshot(data=mock_vinyl_play3.model_dump())

    response = client.delete("/vinyls/123/plays/play1")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == { "detail": "Vinyl Id does not match Vinyl Play" }
    mock_document.return_value.delete.assert_not_called()
