from unittest.mock import MagicMock, patch

import httpx2 as httpx
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from dependencies.firebase_auth import get_firebase_user_from_token
from schemas.vinyls import DiscogsAlbum, DiscogsRelease, Track

from ..discogs import get_discogs_album, get_discogs_release, limiter, router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

mock_user = {
    "uid": "user678",
    "email": "testuser@example.com"
}
mock_discogs_release = DiscogsRelease(
    id=999,
    master_id=555,
    album="Test Vinyl",
    artist="Test Artist",
    n_sides=2,
    disc_color_text="Black",
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
        position="D1",
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
    genres=["Pop", "Rock"],
    image_url="http://example.com/album-image.jpg",
)

@pytest.fixture(autouse=True)
def run_before_each_test():
    limiter.enabled = False
    app.dependency_overrides[get_firebase_user_from_token] = lambda: mock_user
    yield
    app.dependency_overrides.clear()
    limiter.enabled = True

@pytest.fixture
def mock_Client():
    with patch("dependencies.image_colors.httpx.Client") as mock:
        yield mock

@pytest.fixture
def mock_client(mock_Client):
    return mock_Client.return_value.__enter__.return_value

@patch("routers.discogs.get_settings")
def test_get_discogs_release(mock_get_settings, mock_Client, mock_client):
    mock_release_result = {
        "id": 999,
        "master_id": 555,
        "title": "Test Vinyl",
        "artists": [{"name": "Test Artist"}],
    }
    mock_client.get.return_value.json.return_value = mock_release_result

    result = get_discogs_release(999)

    assert result == mock_discogs_release
    assert mock_client.get.call_args.args[0] == "https://api.discogs.com/releases/999"

@patch("routers.discogs.get_settings")
def test_get_discogs_release_full(mock_get_settings, mock_Client, mock_client):
    mock_release_result = {
        "id": 999,
        "master_id": 555,
        "title": "Test Vinyl",
        "artists": [{"name": "Test Artist"}],
        "year": 2025,
        "genres": ["Pop", "Rock"],
        "images": [{"uri": "http://example.com/release-image.jpg"}],
        "formats": [{"text": "Orange marbled"}],
        "identifiers": [{"value": "1234567890"}],
        "tracklist": [{"position": "D1", "type_": "track", "title": "Test Track", "duration": "3:45"}],
    }
    mock_client.get.return_value.json.return_value = mock_release_result

    result = get_discogs_release(999)

    assert result == mock_discogs_release_full
    assert mock_client.get.call_args.args[0] == "https://api.discogs.com/releases/999"

@patch("routers.discogs.get_settings")
def test_get_discogs_release_numeric_track_position(mock_get_settings, mock_Client, mock_client):
    mock_release_result = {
        "id": 999,
        "master_id": 555,
        "title": "Test Vinyl",
        "artists": [{"name": "Test Artist"}],
        "formats": [],
        "tracklist": [{"position": "1", "type_": "track", "title": "Test Track", "duration": "3:45"}],
    }
    mock_client.get.return_value.json.return_value = mock_release_result

    result = get_discogs_release(999)

    assert result and result.model_dump() == {**mock_discogs_release.model_dump(), "tracks": [{"position": "1", "type_": "track", "title": "Test Track", "duration": "3:45"}]}
    assert mock_client.get.call_args.args[0] == "https://api.discogs.com/releases/999"

@patch("routers.discogs.get_settings")
def test_get_discogs_release_error(mock_get_settings, mock_Client, mock_client):
    mock_client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock())

    result = get_discogs_release(999)

    assert result is None
    assert mock_client.get.call_args.args[0] == "https://api.discogs.com/releases/999"


@patch("routers.discogs.get_settings")
def test_get_album_release(mock_get_settings, mock_Client, mock_client):
    mock_album_result = {
        "id": 555,
        "title": "Test Vinyl",
        "artists": [{"name": "Test Artist"}],
        "year": 2019,
        "genres": ["Pop", "Rock"],
        "images": [{"uri": "http://example.com/album-image.jpg"}],
    }
    mock_client.get.return_value.json.return_value = mock_album_result

    result = get_discogs_album(555)

    assert result == mock_discogs_album
    assert mock_client.get.call_args.args[0] == "https://api.discogs.com/masters/555"

@patch("routers.discogs.get_settings")
def test_get_album_release_error(mock_get_settings, mock_Client, mock_client):
    mock_client.get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError("Error", request=MagicMock(), response=MagicMock())

    result = get_discogs_album(555)

    assert result is None
    assert mock_client.get.call_args.args[0] == "https://api.discogs.com/masters/555"
 
@patch("routers.discogs.get_discogs_release")
def test_get_release(mock_get_discogs_release):
    mock_get_discogs_release.return_value = mock_discogs_release

    response = client.get("/vinyls/release/999")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_discogs_release.model_dump()

@patch("routers.discogs.get_discogs_album")
def test_get_album(mock_get_discogs_album):
    mock_get_discogs_album.return_value = mock_discogs_album

    response = client.get("/vinyls/album/555")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == mock_discogs_album.model_dump()

@patch("routers.discogs.get_settings")
def test_search_discogs_release(mock_get_settings, mock_Client, mock_client):
    mock_search_result = {
        "id": 999,
        "master_id": 555,
        "title": "Carly Rae Jepsen",
        "year": 2015,
        "genre": ["Pop"],
        "cover_image": "http://example.com/image.jpg",
        "formats": [{"text": "Black"}],
        "barcode": ["1234567890123"]
    }
    mock_client.get.return_value.json.return_value = {
        "results": [mock_search_result]
    }

    response = client.get("/vinyls/search?term=Carly")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == [{
        "release_id": 999,
        "master_id": 555,
        "title": "Carly Rae Jepsen",
        "published": 2015,
        "genres": ["Pop"],
        "image_url": "http://example.com/image.jpg",
        "disc_color_text": "Black",
        "barcode": "1234567890123"
    }]

@patch("routers.discogs.get_settings")
def test_search_discogs_release_empty(mock_get_settings, mock_Client, mock_client):
    response = client.get("/vinyls/search?term=Carly")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == []

@patch("routers.discogs.get_discogs_album")
def test_search_discogs_release_no_term(mock_get_discogs_album):
    mock_get_discogs_album.return_value = mock_discogs_album

    response = client.get("/vinyls/search")
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"message": "Search term of at least length 3 is required"}

@patch("routers.discogs.get_discogs_album")
def test_search_discogs_release_short_term(mock_get_discogs_album):
    mock_get_discogs_album.return_value = mock_discogs_album

    response = client.get("/vinyls/search?term=ab")
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {"message": "Search term of at least length 3 is required"}
