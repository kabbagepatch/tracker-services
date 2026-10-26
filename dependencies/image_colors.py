from io import BytesIO
from urllib.parse import urlparse

import httpx2 as httpx
from PIL import Image

from dependencies.colorgram import extract


def get_top_colors(image_url):
    if not image_url:
        return []

    parsed_url = urlparse(image_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "i.discogs.com":
        return []
    try:
        with httpx.stream("GET", image_url, timeout=10) as response:
            response.raise_for_status()
            data = b""
            for chunk in response.iter_bytes():
                data += chunk
                if len(data) > 5_000_000:
                    return []
        image = Image.open(BytesIO(data))
        if image.width * image.height > 20_000_000:
            return []
        image.thumbnail((100, 100))

        colors = extract(image, 10)
        return [color.hex for color in colors]
    except Exception as e:  # noqa: BLE001
        print("Error opening image", e)
        return []
