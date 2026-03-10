"""Image understanding tool for model-driven vision requests."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Callable

from nanobot.agent.tools.base import Tool
from nanobot.utils.helpers import detect_image_mime


def _resolve_path(path: str, workspace: Path | None = None, allowed_dir: Path | None = None) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute() and workspace:
        p = workspace / p
    resolved = p.resolve()
    if allowed_dir:
        try:
            resolved.relative_to(allowed_dir.resolve())
        except ValueError as exc:
            raise PermissionError(f"Path {path} is outside allowed directory {allowed_dir}") from exc
    return resolved


class ImageInspectTool(Tool):
    """Inspect an image by forwarding it as multimodal input to the model."""

    def __init__(
        self,
        provider: Any,
        workspace: Path | None = None,
        allowed_dir: Path | None = None,
        model_getter: Callable[[], str | None] | None = None,
        image_model_getter: Callable[[], str | None] | None = None,
    ):
        self._provider = provider
        self._workspace = workspace
        self._allowed_dir = allowed_dir
        self._model_getter = model_getter or (lambda: None)
        self._image_model_getter = image_model_getter or (lambda: None)

    @staticmethod
    def _provider_default_image_model(model: str | None) -> str | None:
        candidate = (model or "").strip().lower()
        if not candidate:
            return None
        if candidate.startswith(("zhipu/", "zai/")) or "glm" in candidate:
            return "glm-4.6v"
        if candidate.startswith("openai/"):
            return "openai/gpt-4o"
        if candidate.startswith("anthropic/"):
            return "anthropic/claude-3-7-sonnet-latest"
        if candidate.startswith("gemini/"):
            return "gemini/gemini-2.0-flash"
        return None

    @staticmethod
    def _looks_like_provider_error(content: str) -> bool:
        lowered = content.lower()
        return lowered.startswith("error calling llm:") or "badrequest" in lowered or "openaiexception" in lowered

    def _candidate_models(self) -> list[str | None]:
        primary = self._model_getter()
        configured_image = self._image_model_getter()
        inferred = self._provider_default_image_model(primary)
        candidates: list[str | None] = []
        for item in (primary, configured_image, inferred):
            if item not in candidates:
                candidates.append(item)
        return candidates

    @property
    def name(self) -> str:
        return "image_inspect"

    @property
    def description(self) -> str:
        return (
            "Inspect a local image file and answer questions about it. "
            "Use this instead of read_file for images."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Local image path (absolute or workspace-relative)."},
                "question": {
                    "type": "string",
                    "description": "What to analyze in the image.",
                },
            },
            "required": ["path"],
        }

    async def execute(self, path: str, question: str = "", **kwargs: Any) -> str:
        try:
            image_path = _resolve_path(path, self._workspace, self._allowed_dir)
            if not image_path.exists() or not image_path.is_file():
                return f"Error: File not found: {path}"
            raw = image_path.read_bytes()
            mime = detect_image_mime(raw) or (mimetypes.guess_type(str(image_path))[0] or "")
            if not mime.startswith("image/"):
                return f"Error: File is not an image: {path}"
            prompt = question.strip() or "Describe this image in detail."
            data_url = f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"
            payload = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ]
            last_error = "Error: image model call failed."
            for model in self._candidate_models():
                response = await self._provider.chat(
                    messages=payload,
                    tools=[],
                    model=model,
                    temperature=0.2,
                    max_tokens=1200,
                )
                content = str(getattr(response, "content", "") or "").strip()
                if content and not self._looks_like_provider_error(content):
                    return content
                if content:
                    last_error = content
            return last_error
        except PermissionError as exc:
            return f"Error: {exc}"
        except Exception as exc:
            return f"Error inspecting image: {exc}"
