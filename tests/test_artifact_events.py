from fastapi.testclient import TestClient


def test_upload_with_session_id_emits_artifact_created_event(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    runtime = WebRuntime(tmp_path)
    client = TestClient(create_app(runtime=runtime))
    session_id = client.post("/sessions", json={}).json()["session_id"]

    resp = client.post(
        f"/files?session_id={session_id}",
        files={"file": ("spec.md", b"hello", "text/markdown")},
    )
    assert resp.status_code == 200

    queue = runtime._event_queues[session_id]
    event = queue.get_nowait()
    assert event["type"] == "artifact.created"
    assert event["artifact"]["type"] in {"file", "report"}
