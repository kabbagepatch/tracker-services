from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin.auth import verify_id_token, get_user

bearer = HTTPBearer(auto_error=False)

def get_firebase_user_from_token(token: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict | None:
  try:
    if not token:
      raise ValueError("No token")
    user = verify_id_token(token.credentials)
    return user
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="Invalid/Missing credentials",
      headers={"WWW-Authenticate": "Bearer"},
    )

FirebaseUserDep = Annotated[dict, Depends(get_firebase_user_from_token)]
