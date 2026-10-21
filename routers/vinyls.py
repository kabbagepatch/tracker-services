from datetime import datetime

import httpx
from fastapi import APIRouter, HTTPException, Request, Response, status
from firebase_admin import firestore
from google.cloud.firestore import SERVER_TIMESTAMP
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from dependencies.colorgram import get_top_colors
from dependencies.config import settings
from dependencies.firebase_auth import FirebaseUserDep

router = APIRouter(
    prefix="/vinyls",
    tags=["Vinyls"]
)

def db():
    return firestore.client()

VINYLS = "vinyls"
VINYL_PLAYS = "vinyl_plays"

class Track(BaseModel):
    position: str = ''
    type_: str = ''
    title: str = ''
    duration: str = ''

class DiscogsAlbum(BaseModel):
    id: int | str = ''
    album: str
    artist: str
    genres: list[str] = []
    published: int | None = None
    image_url: str = ''

class Common(BaseModel):
    album: str
    artist: str
    genres: list[str] = []
    published: int | None = None
    image_url: str = ''
    tracks: list[Track] = []
    disc_color_text: str = ''
    n_sides: int

class DiscogsRelease(Common):
    id: int
    master_id: int | None = None
    barcode: str | None = None

class VinylData(BaseModel):
    discogs_id: int | None = None
    album: str = Field('', max_length=200)
    artist: str = Field('', max_length=200)
    n_sides: int | None = Field(None, ge=1, le=26)
    disc_color_hex: str = Field('', pattern=r'^(#[0-9a-fA-F]{6})?$')

class Vinyl(Common):
    discogs_release_id: int | str
    discogs_master_id: int | str | None = None
    disc_color_hex: str = ''
    release_image_url: str | None = None
    album_image_url: str | None = None
    favorite: bool = False
    album_colors: list[str] = []
    deleted: bool = False

class VinylPlayData(BaseModel):
    sides: list[int] = Field([], max_length=26)
    timestamp: datetime | None = None

class VinylPlay(BaseModel):
    user_id: str
    vinyl_id: str
    sides: int
    timestamp: str

def get_discogs_release(discogs_id):
    with httpx.Client() as client:
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        discogs_response = client.get(f'https://api.discogs.com/releases/{discogs_id}', headers=headers)
        try: discogs_response.raise_for_status()
        except httpx.HTTPStatusError: return

        data = discogs_response.json()
        disc_color_text = (data.get("formats") and len(data["formats"]) > 0 and data["formats"][0].get("text")) or "Black"
        barcode = data["identifiers"][0].get("value") if data.get("identifiers") else None
        first = (data.get("tracklist") or [{}])[-1].get("position", "")[:1].upper()
        n_sides = ord(first) - ord('A') + 1 if 'A' <= first <= 'Z' else 2
        return DiscogsRelease(
            id=discogs_id,
            master_id=data.get("master_id"),
            album=data.get("title"),
            artist=data["artists"][0].get("name"),
            genres=data.get("genres", []),
            published=data.get("year"),
            image_url=(data.get("images") or [{}])[0].get("uri", ""),
            n_sides=n_sides,
            disc_color_text=disc_color_text,
            barcode=barcode,
            tracks=data["tracklist"]
        )

def get_discogs_album(master_id):
    if not master_id: return

    with httpx.Client() as client:
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

@router.get("/release/{discogs_id}")
@limiter.limit("10/minute")
def get_release(request: Request, discogs_id: int, _: FirebaseUserDep):
    return get_discogs_release(discogs_id)

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
        headers = { "Authorization": f"Discogs key={settings.discogs_key.get_secret_value()}, secret={settings.discogs_secret.get_secret_value()}" }
        discogs_response = client.get(
            'https://api.discogs.com/database/search',
            headers=headers,
            params={ "q": term, "type": "release", "format": "Vinyl" }
        )
        data = discogs_response.json()

        return [({
                "discogs_id": v.get("id"),
                "master_id": v.get("master_id"),
                "title": v.get("title"),
                "published": v.get("year"),
                "genres": v.get("genre"),
                "image_url": v.get("cover_image"),
                "disc_color_text": (v.get("formats") and len(v["formats"]) > 0 and v["formats"][0].get("text")) or "Black",
                "barcode": v.get("barcode") and len(v["barcode"]) > 0 and v.get("barcode")[0],
            }) for v in data.get("results", [])]

@router.post("/", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def add_vinyl(request: Request, data: VinylData, user: FirebaseUserDep, response: Response):
    if not data.discogs_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return { "message": "discogs_id is required. Custom vinyls not supported at the moment" }
    
    discogs_release = get_discogs_release(data.discogs_id)
    if not discogs_release:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return { "message": "Invalid discogs_id. No release found" }
    discogs_album = get_discogs_album(discogs_release.master_id)

    vinyl = Vinyl(
        discogs_release_id = discogs_release.id,
        discogs_master_id = discogs_release.master_id,
        album = discogs_release.album,
        artist = discogs_release.artist,
        n_sides = discogs_release.n_sides,
        disc_color_text = discogs_release.disc_color_text,
        published = discogs_album and discogs_album.published or discogs_release.published,
        genres = discogs_release.genres,
        tracks = discogs_release.tracks,
        image_url = discogs_album and discogs_album.image_url or discogs_release.image_url,
        release_image_url = discogs_release.image_url,
        album_image_url = discogs_album and discogs_album.image_url,
        album_colors = get_top_colors(discogs_album and discogs_album.image_url or discogs_release.image_url)
    )

    doc_ref = db().collection(VINYLS).document()
    vinyl_data = {
        **vinyl.model_dump(),
        "user_id": user["uid"],
        "created_at": SERVER_TIMESTAMP,
        "deleted": False
    }
    doc_ref.create(vinyl_data)
    saved_vinyl = doc_ref.get().to_dict()

    return saved_vinyl | { "id": doc_ref.id }

@router.get("/")
@limiter.limit("30/minute")
def list_vinyls(request: Request, user: FirebaseUserDep):
    docs = (
        db().collection(VINYLS)
        .where(filter=FieldFilter("user_id", "==", user["uid"]))
        .where(filter=FieldFilter("deleted", "==", False))
        .stream()
    )
    result = [doc.to_dict() | { "id": doc.id } for doc in docs]

    return result

@router.get("/activity")
@limiter.limit("30/minute")
def get_user_plays(request: Request, user: FirebaseUserDep):
    play_docs = (
        db().collection(VINYL_PLAYS)
        .where(filter=FieldFilter("user_id", "==", user["uid"]))
        .stream()
    )

    plays = [
        {
            "play_id": doc.id,
            "vinyl_id": d["vinyl_id"],
            "sides": d["sides"],
            "timestamp": d["timestamp"],
        }
        for doc in play_docs
        for d in [doc.to_dict()]
    ]
    if not plays:
        return {"plays": []}

    vinyl_docs = (
        db().collection(VINYLS)
        .where(filter=FieldFilter("user_id", "==", user["uid"]))
        .stream()
    )
    vinyl_map = {}
    for v in vinyl_docs:
        vinyl_map[v.id] = v.to_dict()

    result = []
    for play in plays:
        vinyl = vinyl_map.get(play["vinyl_id"])
        if vinyl is None:
            continue
        result.append({
            "album": vinyl["album"],
            "artist": vinyl["artist"],
            "n_sides": vinyl["n_sides"],
            "image_url": vinyl["image_url"],
            "album_colors": vinyl["album_colors"],
            "deleted": vinyl["deleted"],
            **play,
        })
    def timestamp(r):
        return r["timestamp"]
    result.sort(key=timestamp, reverse=True)

    return result

def get_owned_vinyl(user_id, vinyl_id):
    doc_ref = db().collection(VINYLS).document(vinyl_id)
    doc = doc_ref.get()
    if doc.exists:
        vinyl = doc.to_dict() | { "id": doc.id }
        if vinyl["user_id"] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this vinyl",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if vinyl["deleted"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This vinyl has been deleted",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return Vinyl.model_validate(vinyl), doc_ref
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No vinyl found by that id",
            headers={"WWW-Authenticate": "Bearer"},
        )

@router.get("/{vinyl_id}")
def get_vinyl(vinyl_id, user: FirebaseUserDep):
    vinyl, _ = get_owned_vinyl(user["uid"], vinyl_id)

    return vinyl

@router.put("/{vinyl_id}")
def update_vinyl(vinyl_id, data: VinylData, user: FirebaseUserDep):
    vinyl, doc_ref = get_owned_vinyl(user["uid"], vinyl_id)
    updates = {}
    if data.album: updates["album"] = data.album
    if data.artist: updates["artist"] = data.artist
    if data.n_sides: updates["n_sides"] = data.n_sides
    if data.disc_color_hex: updates["disc_color_hex"] = data.disc_color_hex

    doc_ref.update(updates)

    return vinyl.model_dump() | updates

class Favorite(BaseModel): favorite: bool
@router.put("/{vinyl_id}/favorite")
def update_vinyl_favorite(vinyl_id, data: Favorite, user: FirebaseUserDep):
    vinyl, doc_ref = get_owned_vinyl(user["uid"], vinyl_id)
    doc_ref.update({ "favorite": data.favorite })

    return vinyl.model_dump() | { "favorite": data.favorite }

@router.delete("/{vinyl_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_vinyl(vinyl_id, user: FirebaseUserDep):
    _, doc_ref = get_owned_vinyl(user["uid"], vinyl_id)
    doc_ref.update({ "deleted": True })

@router.post("/{vinyl_id}/plays", status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def play_vinyl(request: Request, vinyl_id, data: VinylPlayData, user: FirebaseUserDep):
    vinyl, _ = get_owned_vinyl(user["uid"], vinyl_id)
    sides = data.sides if data.sides.__len__() > 0 else list(range(1, vinyl.n_sides + 1))
    timestamp = data.timestamp or SERVER_TIMESTAMP

    doc_ref = db().collection(VINYL_PLAYS).document()
    play_data = {
        "user_id": user["uid"],
        "vinyl_id": vinyl_id,
        "sides": sides,
        "timestamp": timestamp,
    }
    doc_ref.create(play_data)

    return doc_ref.get().to_dict() | {
        "play_id": doc_ref.id,
        "album": vinyl.album,
        "artist": vinyl.artist,
        "image_url": vinyl.image_url,
        "n_sides": vinyl.n_sides,
        "album_colors": vinyl.album_colors
    }

@router.get("/{vinyl_id}/plays")
def get_vinyl_plays(vinyl_id, user: FirebaseUserDep):
    vinyl, _ = get_owned_vinyl(user["uid"], vinyl_id)
    docs = (
        db().collection(VINYL_PLAYS)
        .where(filter=FieldFilter("user_id", "==", user["uid"]))
        .where(filter=FieldFilter("vinyl_id", "==", vinyl_id))
        .stream()
    )
    plays = [{
        "play_id": doc.id,
        "sides": doc.to_dict()["sides"],
        "timestamp": doc.to_dict()["timestamp"]
    } for doc in docs]

    return {
        "album": vinyl.album,
        "artist": vinyl.artist,
        "n_sides": vinyl.n_sides,
        "image_url": vinyl.image_url,
        "plays": plays
    }

@router.delete("/{vinyl_id}/plays/{play_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_play(vinyl_id, play_id, user: FirebaseUserDep):
    doc_ref = db().collection(VINYL_PLAYS).document(play_id)
    doc = doc_ref.get()
    if doc.exists:
        vinyl_play = doc.to_dict() | { "id": doc.id }
        if vinyl_play["user_id"] != user["uid"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this vinyl",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if vinyl_play["vinyl_id"] != vinyl_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vinyl Id does not match Vinyl Play",
                headers={"WWW-Authenticate": "Bearer"},
            )

        doc_ref.delete()
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No vinyl found by that id",
            headers={"WWW-Authenticate": "Bearer"},
        )
