from dotenv import load_dotenv; load_dotenv()
from firebase import init_firebase; init_firebase()

from fastapi import FastAPI
from middleware.process_time import ProcessTimeMiddleware
from routers.health import router as health_router
from dependencies.firebase_auth import FirebaseUserDep

app = FastAPI()
app.include_router(health_router)
app.add_middleware(ProcessTimeMiddleware)

@app.get("/")
async def root():
  return {"message": "Welcome to Tracker Services"}

@app.get("/user")
async def get_userid(user: FirebaseUserDep):
    """gets the firebase connected user"""
    return user
