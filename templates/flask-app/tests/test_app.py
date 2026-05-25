from app import app


def test_index():
    client = app.test_client()
    r = client.get("/")
    assert r.status_code == 200
    assert "Flask" in r.get_data(as_text=True)


def test_health():
    client = app.test_client()
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
