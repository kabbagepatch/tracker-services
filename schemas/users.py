from pydantic import BaseModel, Field


class UserInput(BaseModel):
    name: str = ""

class UserResponse(UserInput):
    email: str = ""
    vinyl_limit: int = Field(default=1000, ge=1)
    anonymous_discogs_requests_remaining: int = Field(default=20)

class User(UserResponse):
    uid: str = ''
    admin: bool = Field(default=False)
