from fastapi import APIRouter

router = APIRouter()

@router.get("/health", tags=["health"])
def health():
  return { "message": "We are live!", "version": "0.1.0" }
