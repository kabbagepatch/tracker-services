from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin.auth import verify_id_token

from dependencies.users import create_user, get_user_data

bearer = HTTPBearer(auto_error=False)

UNVERIFIED_ROUTES = {"POST /users/", "GET /users/me", "PUT /users/me"}
SECURE_ROUTES = {"POST /users/", "POST /vinyls/", "GET /vinyls/album/{album_id}", "GET /vinyls/release/{release_id}", "GET /vinyls/search"}
ADMIN_ROUTES = {"GET /users/", "GET /users/{uid}", "DELETE /users/{uid}"}

def verify_user(request: Request, token: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> dict:
    route = request.scope.get("route")
    method = request.scope.get("method")
    is_secure_route = bool(route and f"{method} {route.path}" in SECURE_ROUTES)
    try:
        if not token:
            raise ValueError("No token")
        user = verify_id_token(token.credentials, clock_skew_seconds=60, check_revoked=is_secure_route)
    except Exception as e:  # noqa: BLE001
        print(f"Error occurred while verifying token: {e}")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid/Missing credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    is_guest = user.get("firebase", {}).get("sign_in_provider") == "anonymous"
    user_data = get_user_data(user["uid"])

    if route and f"{method} {route.path}" in ADMIN_ROUTES and (not user_data or not user_data.admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource",
        )

    if (not route or f"{method} {route.path}" != "POST /users/") and not user_data:
        create_user(
            uid=user["uid"],
            email=user.get("email", ""),
            is_guest=is_guest
        )

    is_exempt_route = bool(route and f"{method} {route.path}" in UNVERIFIED_ROUTES)
    if not is_guest and not is_exempt_route and not user.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
        )

    request.state.uid = user["uid"]
    user["is_guest"] = is_guest
    user["user_data"] = user_data.model_dump() if user_data else None

    return user

VerifyUserDep = Annotated[dict, Depends(verify_user)]
