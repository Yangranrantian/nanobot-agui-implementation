from fastapi.testclient import TestClient


def test_upload_file_returns_file_metadata(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    client = TestClient(create_app(runtime=WebRuntime(tmp_path)))

    resp = client.post("/files", files={"file": ("note.txt", b"hello", "text/plain")})
    assert resp.status_code == 200
    assert resp.json()["mime_type"] == "text/plain"
