from fastapi.testclient import TestClient


def test_upload_file_returns_file_metadata(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    client = TestClient(create_app(runtime=WebRuntime(tmp_path)))

    resp = client.post("/files", files={"file": ("note.txt", b"hello", "text/plain")})
    assert resp.status_code == 200
    assert resp.json()["mime_type"] == "text/plain"


def test_download_uploaded_file_by_file_id(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    client = TestClient(create_app(runtime=WebRuntime(tmp_path)))

    uploaded = client.post("/files", files={"file": ("pic.png", b"fakepng", "image/png")})
    assert uploaded.status_code == 200
    file_id = uploaded.json()["file_id"]

    downloaded = client.get(f"/files/{file_id}")
    assert downloaded.status_code == 200
    assert downloaded.content == b"fakepng"
    assert downloaded.headers["content-type"].startswith("image/png")


def test_download_file_returns_404_when_missing(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    client = TestClient(create_app(runtime=WebRuntime(tmp_path)))

    missing = client.get("/files/file_missing")
    assert missing.status_code == 404


def test_upload_creates_artifact_event_and_artifact_metadata(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    client = TestClient(create_app(runtime=WebRuntime(tmp_path)))

    resp = client.post("/files", files={"file": ("spec.md", b"hello", "text/markdown")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact"]["type"] in {"file", "report"}
    assert body["artifact"]["metadata"]["runtime"]["mode"] == "path"


def test_image_upload_artifact_metadata_keeps_multimodal_mode(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    client = TestClient(create_app(runtime=WebRuntime(tmp_path)))

    resp = client.post("/files", files={"file": ("pic.png", b"fakepng", "image/png")})
    assert resp.status_code == 200
    body = resp.json()
    assert body["artifact"]["type"] == "image"
    assert body["artifact"]["metadata"]["runtime"]["mode"] == "image"
