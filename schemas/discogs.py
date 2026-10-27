from pydantic import BaseModel


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

class DiscogsRelease(BaseModel):
    id: int
    master_id: int | None = None
    album: str
    artist: str
    n_sides: int
    genres: list[str] = []
    published: int | None = None
    image_url: str = ''
    tracks: list[Track] = []
    disc_color_text: str = ''
    barcode: str | None = None

class DiscogsSearchResult(BaseModel):
    release_id: int
    master_id: int | None = None
    title: str
    published: int | None = None
    genres: list[str] = []
    image_url: str = ''
    disc_color_text: str = ''
    barcode: str | None = None
