from fastapi import FastAPI
from fastapi.testclient import TestClient

from ..health import router

app = FastAPI()
app.include_router(router)
client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == { "message": "We are live!", "version": "0.1.0" }
