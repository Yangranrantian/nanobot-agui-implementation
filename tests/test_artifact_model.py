def test_artifact_model_supports_code_image_link_diagram_report_file():
    from nanobot.web.models import Artifact

    artifact = Artifact(
        artifact_id="art_1",
        type="diagram",
        title="architecture.mmd",
        source="generated",
        path="workspace/architecture.mmd",
        mime_type="text/plain",
        preview_text="Architecture diagram",
        metadata={"diagram_format": "mermaid"},
    )
    assert artifact.type == "diagram"
    assert artifact.metadata["diagram_format"] == "mermaid"
