from dotenv import load_dotenv; load_dotenv()
from firebase import init_firebase; init_firebase()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.process_time import ProcessTimeMiddleware
from routers.health import router as health_router
from routers.users import router as users_router
from routers.vinyls import router as vinyls_router

from dependencies.config import settings

origins = [
    settings.frontend_url,
]

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ProcessTimeMiddleware)
app.include_router(health_router)
app.include_router(users_router)
app.include_router(vinyls_router)

@app.get("/")
async def root():
    return {"message": "Welcome to Tracker Services"}
