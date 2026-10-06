from fastapi import APIRouter, status, Response
from firebase_admin import firestore
from pydantic import BaseModel
import httpx

from dependencies.firebase_auth import FirebaseUserDep

db = firestore.client()
router = APIRouter(
  prefix="/vinyls",
  tags=["Vinyls"]
)

class VinylData(BaseModel):
  discogs_id: int | str
  album: str = ''
  artist: str = ''
  n_sides: int = 2
  disc_color_hex: str = ''

class Track(BaseModel):
  position: str = ''
  type_: str = ''
  title: str = ''
  duration: str = ''

class DiscogsAlbum(BaseModel):
  id: int | str = ''
  album: str
  artist: str
  genres: list[str]
  published: int
  image_url: str

class Common(BaseModel):
  album: str
  artist: str
  genres: list[str]
  published: int
  image_url: str
  tracks: list[Track]
  disc_color_text: str = ''
  n_sides: int

class DiscogsRelease(Common):
  id: int | str
  master_id: int | str
  barcode: str = ''

class Vinyl(Common):
  discogs_release_id: int | str
  discogs_master_id: int | str
  disc_color_hex: str = ''
  release_image_url: str = ''
  album_image_url: str = ''
  favorite: bool = False
  albumColors: list[str] = []

async def get_discogs_release(discogs_id):
  async with httpx.AsyncClient() as client:
    discogs_response = await client.get(f'https://api.discogs.com/releases/{discogs_id}')
    try: discogs_response.raise_for_status()
    except: return

    data = discogs_response.json()

    disc_color_text = (data.get("formats") and len(data["formats"]) > 0 and data["formats"][0].get("text")) or "Black"
    barcode = data["identifiers"][0].get("value") if data.get("identifiers") else None

    return DiscogsRelease(
      id=discogs_id,
      master_id=data.get("master_id"),
      album=data.get("title"),
      artist=data["artists"][0].get("name"),
      genres=data.get("genres"),
      published=data.get("year"),
      image_url=data["images"][0].get("uri"),
      n_sides=ord(data["tracklist"][-1]["position"][0]) - ord('A') + 1,
      disc_color_text=disc_color_text,
      barcode=barcode,
      tracks=data["tracklist"]
    )

async def get_discogs_album(master_id):
  if not master_id: return

  async with httpx.AsyncClient() as client:
    discogs_response = await client.get(f'https://api.discogs.com/masters/{master_id}')
    data = discogs_response.json()

    return DiscogsAlbum(
      id=master_id,
      album=data.get("title"),
      artist=data["artists"][0].get("name"),
      genres=data.get("genres"),
      published=data.get("year"),
      image_url=data["images"][0].get("uri")
    )

@router.get("/release/{discogs_id}")
async def get_release(discogs_id, _: FirebaseUserDep):
  return await get_discogs_release(discogs_id)

@router.get("/album/{master_id}")
async def get_album(master_id, _: FirebaseUserDep):
  return await get_discogs_album(master_id)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def add_vinyl(data: VinylData, user: FirebaseUserDep, response: Response):
  if not data.discogs_id:
    response.status_code = status.HTTP_400_BAD_REQUEST
    return { "message": "discogs_id is required. Custom vinyls not supported at the moment" }
  
  discogs_release = await get_discogs_release(data.discogs_id)
  if not discogs_release:
    response.status_code = status.HTTP_400_BAD_REQUEST
    return { "message": "Invalid discogs_id. No release found" }
  discogs_album = await get_discogs_album(discogs_release.master_id)

  vinyl = Vinyl(
    discogs_release_id = discogs_release.id,
    discogs_master_id = discogs_release.master_id,
    album = discogs_release.album,
    artist = discogs_release.artist,
    n_sides = discogs_release.n_sides,
    disc_color_text = discogs_release.disc_color_text,
    published = discogs_release.published,
    genres = discogs_release.genres,
    tracks = discogs_release.tracks,
    image_url = discogs_album.image_url or discogs_release.image_url,
    release_image_url = discogs_release.image_url,
    album_image_url = discogs_album.image_url,
  )

  doc_ref = db.collection("vinyls").document()
  vinyl_data = {
    **vinyl.model_dump(),
    "user_id": user["uid"],
    "created_at": firestore.SERVER_TIMESTAMP,
  }
  doc_ref.create(vinyl_data)

  return { "message": f'Vinyl {doc_ref.id} added to user {user["uid"]}!' }
