from io import BytesIO
from unittest.mock import patch

import httpx2 as httpx
import pytest
from PIL import Image

from ..image_colors import get_top_colors

IMAGE_URL = "https://i.discogs.com/abc/cover.jpg"

def png_bytes(color=(200, 50, 100), size=(10, 10)):
    buf = BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()

@pytest.fixture
def mock_stream():
    with patch("dependencies.image_colors.httpx.stream") as mock:
        yield mock

@pytest.fixture
def mock_response(mock_stream):
    return mock_stream.return_value.__enter__.return_value

def test_get_top_colors(mock_stream, mock_response):
    mock_response.iter_bytes.return_value = [png_bytes()]

    assert get_top_colors(IMAGE_URL) == ["#c83264"]
    mock_stream.assert_called_once_with("GET", IMAGE_URL, timeout=10)

@pytest.mark.parametrize("image_url", [
    None,
    "",
    "http://i.discogs.com/abc/cover.jpg",
    "https://example.com/cover.jpg",
    "https://i.discogs.com.evil.com/cover.jpg",
    "https://evil.com/?i.discogs.com",
    "file:///etc/passwd",
])
def test_get_top_colors_rejected_url(mock_stream, image_url):
    assert get_top_colors(image_url) == []
    mock_stream.assert_not_called()

def test_get_top_colors_http_error(mock_response):
    mock_response.raise_for_status.side_effect = httpx.HTTPError("404")

    assert get_top_colors(IMAGE_URL) == []
    mock_response.iter_bytes.assert_not_called()

def test_get_top_colors_too_large_download(mock_response):
    mock_response.iter_bytes.return_value = [b"0" * 3_000_000, b"0" * 3_000_000]

    assert get_top_colors(IMAGE_URL) == []

@patch("dependencies.image_colors.extract")
def test_get_top_colors_too_many_pixels(mock_extract, mock_response):
    mock_response.iter_bytes.return_value = [png_bytes(size=(5000, 5000))]

    assert get_top_colors(IMAGE_URL) == []
    mock_extract.assert_not_called()

def test_get_top_colors_not_an_image(mock_response):
    mock_response.iter_bytes.return_value = [b"not an image"]

    assert get_top_colors(IMAGE_URL) == []
