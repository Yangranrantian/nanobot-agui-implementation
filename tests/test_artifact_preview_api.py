from fastapi.testclient import TestClient


def test_artifact_preview_endpoint_returns_typed_preview_payload(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    runtime = WebRuntime(tmp_path)
    client = TestClient(create_app(runtime=runtime))

    upload_resp = client.post("/files", files={"file": ("note.txt", b"hello", "text/plain")})
    assert upload_resp.status_code == 200
    artifact_id = upload_resp.json()["artifact"]["artifact_id"]

    resp = client.get(f"/artifacts/{artifact_id}")
    assert resp.status_code == 200
    assert "viewer_type" in resp.json()
