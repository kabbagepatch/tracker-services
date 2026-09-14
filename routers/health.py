from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["health"])
def hello():
  return "We are live!"
