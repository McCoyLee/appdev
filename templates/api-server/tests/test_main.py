from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_hello():
    r = client.get("/hello/world")
    assert r.status_code == 200
    assert r.json() == {"message": "hello, world"}
