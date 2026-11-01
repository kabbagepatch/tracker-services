from fastapi import APIRouter, HTTPException, Response, status
from firebase_admin import auth, firestore
from firebase_admin.exceptions import FirebaseError
from google.cloud.firestore_v1.base_query import FieldFilter

from dependencies.firebase_auth import VerifyUserDep
from dependencies.users import admin_check, create_user, get_user_data
from routers.vinyls import VINYL_PLAYS, VINYLS
from schemas.users import User, UserInput, UserResponse

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

def db():
    return firestore.client()

@router.post("/")
def sign_up(data: UserInput, user: VerifyUserDep, response: Response):
    created = create_user(
        uid=user["uid"],
        name=data.name,
        email=user.get("email", ''),
        is_guest=user.get("is_guest", False)
    )

    if created:
        response.status_code = status.HTTP_201_CREATED
        return { "message": "User " + user["uid"] + " created!" }

    return { "message": "User " + user["uid"] + " already exists" }

@router.get("/")
def list_users(user: VerifyUserDep) -> list[User]:
    admin_check(user)
    users_ref = db().collection("users")
    docs = users_ref.stream()

    result = [User.model_validate(doc.to_dict() | { "uid": doc.id }) for doc in docs]
    
    return result

@router.get("/me")
def get_me(user: VerifyUserDep) -> UserResponse:
    user_data = user.get("user_data")
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return user_data

@router.put("/me")
def update_me(data: UserInput, user: VerifyUserDep) -> UserResponse:
    doc_ref = db().collection("users").document(user["uid"])
    if not user.get("email", None):
        raise HTTPException(status_code=400, detail="Email is required for updating user profile")

    user_updates = User(
        uid=user["uid"],
        name=data.name,
        email=user["email"],
        vinyl_limit=1000,
    )
    doc_ref.update(user_updates.model_dump())

    return user_updates

@router.get("/{uid}")
def get_user(uid: str, user: VerifyUserDep) -> UserResponse:
    admin_check(user)
    user_data = get_user_data(uid)
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return user_data

@router.delete("/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(uid: str, user: VerifyUserDep):
    if uid == user["uid"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    admin_check(user)

    batch = db().batch()
    vinyls_doc_ref = db().collection(VINYLS).where(filter=FieldFilter("user_id", "==", uid))
    for vinyl_doc in vinyls_doc_ref.stream():
        batch.delete(vinyl_doc.reference)

    vinyl_plays_doc_ref = db().collection(VINYL_PLAYS).where(filter=FieldFilter("user_id", "==", uid))
    for vinyl_play_doc in vinyl_plays_doc_ref.stream():
        batch.delete(vinyl_play_doc.reference)

    user_ref = db().collection("users").document(uid)
    batch.delete(user_ref)

    batch.commit()

    try:
        auth.delete_user(uid)
    except FirebaseError:
        raise HTTPException(status_code=500, detail="Failed to delete user from authentication. Database deletion may have occurred.")
