from fastapi import HTTPException, status
from firebase_admin import firestore
from google.api_core import exceptions
from google.cloud.firestore import SERVER_TIMESTAMP

from schemas.users import User


def db():
    return firestore.client()

def create_user(uid, name='', email='', is_guest=False):
    try:
        doc_ref = db().collection("users").document(uid)
        new_user = User(
            uid=uid,
            name=name,
            email=email,
            vinyl_limit=10 if is_guest else 1000,
        )
        doc_ref.create({
            **new_user.model_dump(),
            "created_at": SERVER_TIMESTAMP
        })

        return True
    except exceptions.AlreadyExists:
        return False

def get_user_data(uid):
    doc_ref = db().collection("users").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        return None

    return User.model_validate(doc.to_dict())

def set_discogs_requests(uid, value):
    doc_ref = db().collection("users").document(uid)
    update_data = {
        "anonymous_discogs_requests_remaining": value
    }
    doc_ref.update(update_data)

def admin_check(user):
    if not user.get("user_data") or not user["user_data"].get("admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is not an admin")
