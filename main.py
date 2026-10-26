from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.extension import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from dependencies.config import get_settings
from firebase import init_firebase
from middleware.process_time import ProcessTimeMiddleware
from routers.discogs import router as discogs_router
from routers.health import router as health_router
from routers.users import router as users_router
from routers.vinyls import router as vinyls_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firebase()
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler) # pyright: ignore[reportArgumentType]
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[get_settings().frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ProcessTimeMiddleware)

app.include_router(discogs_router)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(vinyls_router)

@app.get("/")
async def root():
    return {"message": "Welcome to Tracker Services"}
