from datetime import datetime

from pydantic import BaseModel, Field


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
    n_sides: int
    genres: list[str] = []
    published: int | None = None
    image_url: str = ''
    tracks: list[Track] = []
    disc_color_text: str = ''

class DiscogsRelease(Common):
    id: int
    master_id: int | None = None
    barcode: str | None = None

class Vinyl(Common):
    discogs_release_id: int | str
    discogs_master_id: int | str | None = None
    disc_color_hex: str = ''
    release_image_url: str = ''
    album_image_url: str | None = None
    favorite: bool = False
    album_colors: list[str] = []
    deleted: bool = False

class VinylData(BaseModel):
    release_id: int | None = None
    album: str = Field('', max_length=200)
    artist: str = Field('', max_length=200)
    n_sides: int | None = Field(None, ge=1, le=26)
    disc_color_hex: str = Field('', pattern=r'^(#[0-9a-fA-F]{6})?$')

class VinylPlay(BaseModel):
    user_id: str
    vinyl_id: str
    sides: list[int]
    timestamp: str

class VinylPlayData(BaseModel):
    sides: list[int] = Field([], max_length=26)
    timestamp: datetime | None = None
