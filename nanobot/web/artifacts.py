from __future__ import annotations

from pathlib import Path

from .models import Artifact


def resolve_artifact_preview(artifact: Artifact) -> dict:
    viewer_type = _viewer_type_for(artifact.type)
    payload = {
        "artifact_id": artifact.artifact_id,
        "type": artifact.type,
        "title": artifact.title,
        "viewer_type": viewer_type,
        "mime_type": artifact.mime_type,
        "source": artifact.source,
    }

    if artifact.url:
        payload["url"] = artifact.url

    if artifact.path:
        payload["path"] = artifact.path
        text_content = _read_text_preview(artifact.path)
        if text_content is not None and viewer_type in {"text", "code", "diagram"}:
            payload["content"] = text_content

    if artifact.preview_text:
        payload["preview_text"] = artifact.preview_text

    if artifact.type == "diagram":
        payload["view_modes"] = ["rendered", "source"]
    return payload


def _viewer_type_for(artifact_type: str) -> str:
    mapping = {
        "file": "text",
        "report": "text",
        "code": "code",
        "image": "image",
        "link": "link",
        "diagram": "diagram",
    }
    return mapping.get(artifact_type, "text")


def _read_text_preview(path: str) -> str | None:
    try:
        target = Path(path)
        if not target.exists() or not target.is_file():
            return None
        return target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
