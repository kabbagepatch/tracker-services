import logging

import httpx2 as httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from dependencies.config import get_settings
from dependencies.firebase_auth import VerifyUserDep, verify_app_check
from dependencies.limiter import limiter
from dependencies.users import set_discogs_requests
from schemas.discogs import DiscogsAlbum, DiscogsRelease, DiscogsSearchResult

router = APIRouter(
    prefix="/vinyls",
    tags=["Vinyls"],
    dependencies=[Depends(verify_app_check)]
)

logger = logging.getLogger(__name__)

def get_discogs_release(release_id):
    with httpx.Client() as client:
        settings = get_settings()
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        try:
            discogs_response = client.get(f'https://api.discogs.com/releases/{release_id}', headers=headers)
            discogs_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Error getting discogs release: {e}")
            return
        except Exception:
            logger.exception("Error getting discogs release")
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
        try:
            discogs_response = client.get(f'https://api.discogs.com/masters/{master_id}', headers=headers)
            discogs_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Error getting discogs master: {e}")
            return
        except Exception:
            logger.exception("Error getting discogs master")
            return

        data = discogs_response.json()
        return DiscogsAlbum(
            id=master_id,
            album=data.get("title"),
            artist=data["artists"][0].get("name"),
            genres=data.get("genres", []),
            published=data.get("year"),
            image_url=(data.get("images") or [{}])[0].get("uri", "")
        )

@router.get("/release/{release_id}")
@limiter.limit("10/minute")
@limiter.shared_limit("50/minute", scope="discogs_group", key_func=lambda: "discogs")
def get_release(request: Request, release_id: int, _: VerifyUserDep) -> DiscogsRelease:
    release = get_discogs_release(release_id)
    if not release:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Release not found")
    return release

@router.get("/album/{master_id}")
@limiter.limit("10/minute")
@limiter.shared_limit("50/minute", scope="discogs_group", key_func=lambda: "discogs")
def get_album(request: Request, master_id: int, _: VerifyUserDep) -> DiscogsAlbum:
    album = get_discogs_album(master_id)
    if not album:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Album not found")
    return album

@router.get("/search")
@limiter.limit("10/minute")
@limiter.shared_limit("50/minute", scope="discogs_group", key_func=lambda: "discogs")
def search_discogs_release(request: Request, user: VerifyUserDep, response: Response, term: str = '') -> list[DiscogsSearchResult]:
    if len(term) <= 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search term of at least length 3 is required")

    user_data = user.get("user_data")
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="There was an error retrieving your user data. Please try again later."
        )
    requests_remaining = user_data.get("anonymous_discogs_requests_remaining", 0)
    if user.get("is_guest", True) and requests_remaining <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest Discogs requests limit reached.",
        )

    with httpx.Client() as client:
        settings = get_settings()
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        try:
            discogs_response = client.get(
                'https://api.discogs.com/database/search',
                headers=headers,
                params={ "q": term, "type": "release", "format": "Vinyl" }
            )
            discogs_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.warning(f"Error getting search results: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error getting search results.",
            )
        except Exception:
            logger.exception("Error getting search results")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error getting search results.",
            )

    if user.get("is_guest", True):
        set_discogs_requests(user["uid"], requests_remaining - 1)

    data = discogs_response.json()

    return [DiscogsSearchResult(
        release_id=v.get("id"),
        master_id=v.get("master_id"),
        title=v.get("title"),
        published=v.get("year"),
        genres=v.get("genre"),
        image_url=v.get("cover_image"),
        disc_color_text=(v.get("formats") and len(v["formats"]) > 0 and v["formats"][0].get("text")) or "Black",
        barcode=(v.get("barcode") and len(v["barcode"]) > 0) and v.get("barcode")[0] or '',
    ) for v in data.get("results", [])]
