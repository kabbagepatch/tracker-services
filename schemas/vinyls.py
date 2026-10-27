from datetime import datetime

from pydantic import BaseModel, Field

from schemas.discogs import Track


class VinylCreate(BaseModel):
    release_id: int

class VinylUpdate(BaseModel):
    album: str = Field(default='', max_length=200)
    artist: str = Field(default='', max_length=200)
    n_sides: int | None = Field(default=None, ge=1, le=26)
    disc_color_hex: str = Field(default='', pattern=r'^(#[0-9a-fA-F]{6})?$')

class VinylData(VinylUpdate):
    genres: list[str] = []
    published: int | None = None
    image_url: str = ''
    tracks: list[Track] = []
    disc_color_text: str = ''
    favorite: bool = False
    album_colors: list[str] = []

class VinylResponse(VinylData):
    id: str = ''

class Vinyl(VinylResponse):
    user_id: str
    discogs_release_id: int | str
    discogs_master_id: int | str | None = None
    release_image_url: str = ''
    album_image_url: str | None = None
    deleted: bool = False

class VinylPlayCreate(BaseModel):
    sides: list[int] = Field(default=[], max_length=26)
    timestamp: datetime | str = ''

class VinylPlay(VinylPlayCreate):
    user_id: str
    vinyl_id: str

class VinylPlayResponse(VinylPlayCreate):
    vinyl_id: str
    play_id: str = ''
    album: str = Field(default='', max_length=200)
    artist: str = Field(default='', max_length=200)
    n_sides: int | None = Field(default=None, ge=1, le=26)
    image_url: str = ''
    album_colors: list[str] = []
    deleted: bool = False

class VinylPlayItem(BaseModel):
    play_id: str
    sides: list[int]
    timestamp: datetime | str
class VinylPlaysResponse(BaseModel):
    vinyl_id: str
    album: str = Field(default='', max_length=200)
    artist: str = Field(default='', max_length=200)
    n_sides: int | None = Field(default=None, ge=1, le=26)
    image_url: str = ''
    plays: list[VinylPlayItem] = []
