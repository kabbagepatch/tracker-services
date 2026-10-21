from fastapi import APIRouter, Response, status
from firebase_admin import firestore
from google.api_core import exceptions
from google.cloud.firestore import SERVER_TIMESTAMP
from pydantic import BaseModel

from dependencies.firebase_auth import FirebaseUserDep

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

def db():
    return firestore.client()

class UserData(BaseModel):
    name: str

@router.post("/")
async def create_user(data: UserData, user: FirebaseUserDep, response: Response):
    try: 
        doc_ref = db().collection("users").document(user["uid"])
        doc_ref.create({ "name": data.name, "email": user["email"], "created_at": SERVER_TIMESTAMP })
        response.status_code = status.HTTP_201_CREATED

        return { "message": "User " + user["uid"] + " created!" }
    except exceptions.AlreadyExists:
        return { "message": "User " + user["uid"] + " already exists" }

@router.get("/me")
async def get_user(user: FirebaseUserDep):
    """gets the firebase connected user"""
    return user
