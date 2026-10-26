import httpx2 as httpx
from fastapi import APIRouter, Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from dependencies.config import get_settings
from dependencies.firebase_auth import FirebaseUserDep
from schemas.vinyls import DiscogsAlbum, DiscogsRelease

router = APIRouter(
    prefix="/vinyls",
    tags=["Vinyls"]
)

def get_discogs_release(release_id):
    with httpx.Client() as client:
        settings = get_settings()
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        discogs_response = client.get(f'https://api.discogs.com/releases/{release_id}', headers=headers)
        try:
            discogs_response.raise_for_status()
        except httpx.HTTPStatusError:
            return

        data = discogs_response.json()
        disc_color_text = (data.get("formats") and len(data["formats"]) > 0 and data["formats"][0].get("text")) or "Black"
        barcode = data["identifiers"][0].get("value") if data.get("identifiers") else None
        first = (data.get("tracklist") or [{}])[-1].get("position", "")[:1].upper()
        n_sides = ord(first) - ord('A') + 1 if 'A' <= first <= 'Z' else 2
        return DiscogsRelease(
            id=release_id,
            master_id=data.get("master_id"),
            album=data.get("title"),
            artist=data["artists"][0].get("name"),
            genres=data.get("genres", []),
            published=data.get("year"),
            image_url=(data.get("images") or [{}])[0].get("uri", ""),
            n_sides=n_sides,
            disc_color_text=disc_color_text,
            barcode=barcode,
            tracks=data.get("tracklist", []),
        )

def get_discogs_album(master_id):
    if not master_id: return

    with httpx.Client() as client:
        settings = get_settings()
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        discogs_response = client.get(f'https://api.discogs.com/masters/{master_id}', headers=headers)
        try: discogs_response.raise_for_status()
        except httpx.HTTPStatusError: return

        data = discogs_response.json()
        return DiscogsAlbum(
            id=master_id,
            album=data.get("title"),
            artist=data["artists"][0].get("name"),
            genres=data.get("genres", []),
            published=data.get("year"),
            image_url=(data.get("images") or [{}])[0].get("uri", "")
        )

def uid_key(request: Request):
    return getattr(request.state, "uid", None) or get_remote_address(request)
limiter = Limiter(key_func=uid_key)

@router.get("/release/{release_id}")
@limiter.limit("10/minute")
def get_release(request: Request, release_id: int, _: FirebaseUserDep):
    return get_discogs_release(release_id)

@router.get("/album/{master_id}")
@limiter.limit("10/minute")
def get_album(request: Request, master_id: int, _: FirebaseUserDep):
    return get_discogs_album(master_id)

@router.get("/search")
@limiter.limit("10/minute")
def search_discogs_release(request: Request, _: FirebaseUserDep, response: Response, term: str = ''):
    if len(term) <= 2:
        response.status_code = 400
        return { "message": "Search term of at least length 3 is required" }

    with httpx.Client() as client:
        settings = get_settings()
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        discogs_response = client.get(
            'https://api.discogs.com/database/search',
            headers=headers,
            params={ "q": term, "type": "release", "format": "Vinyl" }
        )
        data = discogs_response.json()

        return [({
            "release_id": v.get("id"),
            "master_id": v.get("master_id"),
            "title": v.get("title"),
            "published": v.get("year"),
            "genres": v.get("genre"),
            "image_url": v.get("cover_image"),
            "disc_color_text": (v.get("formats") and len(v["formats"]) > 0 and v["formats"][0].get("text")) or "Black",
            "barcode": v.get("barcode") and len(v["barcode"]) > 0 and v.get("barcode")[0],
        }) for v in data.get("results", [])]
