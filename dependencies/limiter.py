from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def uid_key(request: Request):
    return getattr(request.state, "uid", None) or get_remote_address(request)
limiter = Limiter(key_func=uid_key)
