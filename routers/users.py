from fastapi import APIRouter, Response, status
from firebase_admin import firestore
from google.api_core import exceptions
from pydantic import BaseModel

from dependencies.firebase_auth import FirebaseUserDep

db = firestore.client()
router = APIRouter(
  prefix="/users",
  tags=["Users"]
)

class UserData(BaseModel):
  name: str

@router.post("/")
async def create_user(data: UserData, user: FirebaseUserDep, response: Response):
  try: 
    doc_ref = db.collection("users").document(user["uid"])
    doc_ref.create({ "name": data.name, "email": user["email"], "created_at": firestore.SERVER_TIMESTAMP })
    response.status_code = status.HTTP_201_CREATED

    return { "message": "User " + user["uid"] + " created!" }
  except exceptions.AlreadyExists as e:
    return { "message": "User " + user["uid"] + " already exists" }

@router.get("/me")
async def get_user(user: FirebaseUserDep):
  """gets the firebase connected user"""
  return user
