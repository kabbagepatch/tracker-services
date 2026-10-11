from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin.auth import verify_id_token, get_user

bearer = HTTPBearer(auto_error=False)

def get_firebase_user_from_token(token: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict | None:
    user = {}
    try:
        if not token:
            raise ValueError("No token")
        user = verify_id_token(token.credentials)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid/Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # if not user["email_verified"]:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Email not verified. Get fucked",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    return user

FirebaseUserDep = Annotated[dict, Depends(get_firebase_user_from_token)]
