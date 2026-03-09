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


def test_mermaid_artifact_preview_returns_rendered_and_source_modes(tmp_path):
    from nanobot.web.models import Artifact
    from nanobot.web.runtime import WebRuntime

    runtime = WebRuntime(tmp_path)
    runtime._artifacts["art_mermaid"] = Artifact(
        artifact_id="art_mermaid",
        type="diagram",
        title="graph.mmd",
        source="generated",
        path=str(tmp_path / "graph.mmd"),
        mime_type="text/plain",
        preview_text="graph TD;A-->B",
        metadata={"diagram_format": "mermaid"},
    )
    (tmp_path / "graph.mmd").write_text("graph TD;A-->B", encoding="utf-8")

    preview = runtime.get_artifact_preview("art_mermaid")
    assert preview["viewer_type"] == "diagram"
    assert preview["view_modes"] == ["rendered", "source"]
