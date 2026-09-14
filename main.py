from fastapi import FastAPI
from routers.health import router as health_router

app = FastAPI()
app.include_router(health_router)

@app.get("/")
async def root():
  return {"message": "Hello World"}
