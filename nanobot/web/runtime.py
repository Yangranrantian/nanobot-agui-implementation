from __future__ import annotations

import asyncio
import mimetypes
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from nanobot.session.manager import Session, SessionManager

from .artifacts import resolve_artifact_preview
from .events import make_event
from .files import FileStore
from .interrupts import InterruptEnvelope, InterruptRequest, InterruptResolvedResponse, InterruptResponse
from .models import (
    Artifact,
    FileUploadResponse,
    MessageListResponse,
    MessageRecord,
    RunAcceptedResponse,
    SessionListResponse,
    SessionSummary,
)


def project_status_from_events(events: list[dict]) -> dict:
    active: set[str] = set()
    for event in events:
        payload = event.get("payload", {})
        task_id = payload.get("task_id")
        if not task_id:
            continue
        event_type = str(event.get("type") or "")
        if event_type in {"task.started", "task.updated"}:
            active.add(task_id)
        elif event_type in {"task.completed", "task.failed"}:
            active.discard(task_id)
    return {"active_task_count": len(active)}


class WebRuntime:
    """Thin adapter that exposes browser-facing session operations."""

    _PROVIDER_IMAGE_DEFAULTS = {
        "openai": "openai/gpt-5-mini",
        "anthropic": "anthropic/claude-opus-4-6",
        "google": "gemini/gemini-3-flash-preview",
        "gemini": "gemini/gemini-3-flash-preview",
        "minimax": "minimax/MiniMax-VL-01",
        "zai": "glm-4.6v",
        "zhipu": "glm-4.6v",
    }
    _ZHIPU_VISION_MAX_TOKENS = 16384

    def __init__(
        self,
        workspace: Path,
        agent_loop=None,
        image_model_primary: str | None = None,
        provider_name: str | None = None,
        preview_roots: list[Path] | None = None,
    ):
        self.workspace = Path(workspace)
        self.sessions = SessionManager(self.workspace)
        self.agent_loop = None
        self.image_model_primary = image_model_primary
        self.provider_name = provider_name
        self._event_queues: dict[str, asyncio.Queue[dict]] = {}
        self._pending_interrupts: dict[str, tuple[str, str, asyncio.Future[InterruptResponse], InterruptEnvelope]] = {}
        self._artifacts: dict[str, Artifact] = {}
        self._preview_roots = [p.resolve() for p in (preview_roots or self._default_preview_roots())]
        self._fallback_search_roots = [p.resolve() for p in self._default_fallback_search_roots()]
        self.files = FileStore(self.workspace / "web_uploads")
        if agent_loop is not None:
            self.attach_agent_loop(agent_loop)

    def _default_preview_roots(self) -> list[Path]:
        roots = [self.workspace, self.workspace.parent, self.workspace.parent.parent, Path.home(), Path.home() / ".nanobot" / "workspace"]
        uniq: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            resolved = root.resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(resolved)
        return uniq

    def _default_fallback_search_roots(self) -> list[Path]:
        roots = [self.workspace, self.workspace.parent, self.workspace.parent.parent, Path.home() / ".nanobot" / "workspace"]
        uniq: list[Path] = []
        seen: set[str] = set()
        for root in roots:
            resolved = root.resolve()
            key = str(resolved)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(resolved)
        return uniq

    def attach_agent_loop(self, agent_loop) -> None:
        self.agent_loop = agent_loop
        if hasattr(agent_loop, "sessions"):
            self.sessions = agent_loop.sessions
        if hasattr(agent_loop, "set_interrupt_handler"):
            agent_loop.set_interrupt_handler(self.handle_interrupt)

    @staticmethod
    def session_key(session_id: str) -> str:
        return f"web:{session_id}"

    @staticmethod
    def session_id_from_key(session_key: str) -> str | None:
        prefix = "web:"
        if not session_key.startswith(prefix):
            return None
        return session_key[len(prefix):]

    @staticmethod
    def _is_multimodal_model(model: str | None) -> bool:
        if not model:
            return False
        lower = model.lower()
        return any(token in lower for token in ("4o", "vision", "vl", "4v", "claude-3", "gemini", "glm-4.6v", "minimax-vl"))

    def _normalize_model_for_provider(self, model: str | None) -> str | None:
        if not model:
            return model
        provider = (self.provider_name or "").lower().replace("_", "-")
        if provider in {"zhipu", "zai"} and "/" in model:
            prefix, remainder = model.split("/", 1)
            if prefix.lower() in {"zhipu", "zai"} and remainder:
                return remainder
        return model

    @staticmethod
    def _is_image_attachment(item: dict) -> bool:
        mime = str(item.get("mime_type") or "").lower()
        if mime.startswith("image/"):
            return True
        candidate = item.get("filename") or item.get("path")
        if not candidate:
            return False
        guessed = (mimetypes.guess_type(str(candidate))[0] or "").lower()
        return guessed.startswith("image/")

    def _resolve_media_paths(self, attachments: list[dict]) -> list[str]:
        paths: list[str] = []
        for item in attachments:
            path = item.get("path")
            if not path or not self._is_image_attachment(item):
                continue
            paths.append(path)
        return paths

    @classmethod
    def build_runtime_attachment(cls, filename: str, mime_type: str, path: str) -> dict:
        if cls._is_image_attachment({"filename": filename, "mime_type": mime_type, "path": path}):
            return {"mode": "image", "path": path, "mime_type": mime_type}
        return {"mode": "path", "path": path, "mime_type": mime_type}

    @classmethod
    def _normalize_runtime_attachments(cls, attachments: list[dict]) -> list[dict]:
        normalized: list[dict] = []
        for item in attachments:
            path = str(item.get("path") or "")
            if not path:
                continue
            normalized.append(
                {
                    **item,
                    "runtime": cls.build_runtime_attachment(
                        str(item.get("filename") or ""),
                        str(item.get("mime_type") or ""),
                        path,
                    ),
                }
            )
        return normalized

    def _pick_multimodal_model(self, current_model: str | None) -> str | None:
        current_model = self._normalize_model_for_provider(current_model)

        if self._is_multimodal_model(current_model):
            return current_model

        picked = self.image_model_primary
        if not picked:
            provider = (self.provider_name or "").lower().replace("_", "-")
            if provider:
                picked = self._PROVIDER_IMAGE_DEFAULTS.get(provider, current_model)
            elif current_model and "/" in current_model:
                prefix = current_model.split("/", 1)[0].lower()
                picked = self._PROVIDER_IMAGE_DEFAULTS.get(prefix, current_model)
            else:
                picked = current_model

        return self._normalize_model_for_provider(picked)

    def _vision_max_tokens_cap(self, media_paths: list[str]) -> int | None:
        if not media_paths:
            return None
        provider = (self.provider_name or "").lower().replace("_", "-")
        if provider not in {"zhipu", "zai"}:
            return None
        return self._ZHIPU_VISION_MAX_TOKENS

    def create_session(self) -> SessionSummary:
        session_id = f"sess_{uuid4().hex[:12]}"
        session = self.sessions.get_or_create(self.session_key(session_id))
        self.sessions.save(session)
        self._ensure_event_queue(session_id)
        return self._session_summary(session_id, session)

    def list_sessions(self) -> SessionListResponse:
        items: list[SessionSummary] = []
        for item in self.sessions.list_sessions():
            key = item.get("key", "")
            session_id = self.session_id_from_key(key)
            if not session_id:
                continue
            session = self.sessions.get_or_create(key)
            items.append(self._session_summary(session_id, session))
        return SessionListResponse(items=items)

    def delete_session(self, session_id: str) -> dict:
        key = self.session_key(session_id)
        deleted = self.sessions.delete(key)
        self._event_queues.pop(session_id, None)
        self._pending_interrupts = {
            k: v for k, v in self._pending_interrupts.items() if v[0] != session_id
        }
        if not deleted:
            raise KeyError(session_id)
        return {"status": "deleted", "session_id": session_id}

    def get_messages(self, session_id: str) -> MessageListResponse:
        key = self.session_key(session_id)
        self.sessions.invalidate(key)
        session = self.sessions.get_or_create(key)
        items = [
            MessageRecord(
                role=message.get("role", "assistant"),
                content=message.get("content"),
                timestamp=message.get("timestamp"),
                attachments=message.get("attachments") or [],
            )
            for message in session.messages
        ]
        return MessageListResponse(items=items)

    async def dispatch_message(
        self,
        session_id: str,
        content: str,
        attachments: list[dict],
    ) -> RunAcceptedResponse:
        run_id = f"run_{uuid4().hex[:12]}"
        queue = self._ensure_event_queue(session_id)
        await queue.put(make_event("run.started", run_id=run_id, session_id=session_id))

        if self.agent_loop is not None:
            asyncio.create_task(self._run_agent(session_id, content, attachments, run_id))

        return RunAcceptedResponse(run_id=run_id, session_id=session_id, status="accepted")

    async def _run_agent(self, session_id: str, content: str, attachments: list[dict], run_id: str) -> None:
        media_paths = self._resolve_media_paths(attachments)
        original_model = None
        original_max_tokens = None

        try:
            if media_paths and hasattr(self.agent_loop, "model"):
                original_model = self.agent_loop.model
                picked = self._pick_multimodal_model(original_model)
                if picked and picked != original_model:
                    self.agent_loop.model = picked
                    await self.publish_event(
                        session_id,
                        make_event("model.switched", run_id=run_id, from_model=original_model, to_model=picked),
                    )

            max_tokens_cap = self._vision_max_tokens_cap(media_paths)
            if max_tokens_cap and hasattr(self.agent_loop, "max_tokens"):
                current_max_tokens = getattr(self.agent_loop, "max_tokens")
                if isinstance(current_max_tokens, int) and current_max_tokens > max_tokens_cap:
                    original_max_tokens = current_max_tokens
                    self.agent_loop.max_tokens = max_tokens_cap

            await self.agent_loop.process_direct(
                content,
                session_key=self.session_key(session_id),
                channel="web",
                chat_id=session_id,
                media=media_paths,
                metadata={
                    "attachments": attachments,
                    "runtime_attachments": self._normalize_runtime_attachments(attachments),
                },
                on_event=lambda event: self.publish_event(session_id, {**event, "run_id": event.get("run_id", run_id)}),
            )
        except Exception as exc:
            message = str(exc)
            lower = message.lower()
            if media_paths and ("badrequest" in lower or "zaiexception" in lower or "image" in lower or "vision" in lower):
                provider_name = (self.provider_name or "").lower().replace("_", "-")
                if provider_name in {"zhipu", "zai"}:
                    message = (
                        "Zhipu image parsing failed. Please verify image format (jpg/png/jpeg), "
                        "size <= 5MB, and pixel bounds <= 6000x6000. "
                        "If it still fails, try a public image URL to isolate endpoint parsing issues."
                    )
                else:
                    message = (
                        "Image parsing failed. Please verify you are using a vision-capable model "
                        "(e.g. glm-4.6v) and a provider endpoint that supports multimodal chat."
                    )
            await self.publish_event(
                session_id,
                make_event("error", run_id=run_id, session_id=session_id, message=message),
            )
        finally:
            if original_max_tokens is not None and hasattr(self.agent_loop, "max_tokens"):
                self.agent_loop.max_tokens = original_max_tokens
            if original_model is not None and hasattr(self.agent_loop, "model"):
                self.agent_loop.model = original_model

    async def publish_event(self, session_id: str, event: dict) -> None:
        queue = self._ensure_event_queue(session_id)
        await queue.put(event)

    async def stream_session_events(self, session_id: str) -> AsyncIterator[dict]:
        queue = self._ensure_event_queue(session_id)
        while True:
            yield await queue.get()

    async def handle_interrupt(self, session_key: str, request: InterruptRequest, on_event=None) -> InterruptResponse:
        session_id = self.session_id_from_key(session_key) or session_key
        interrupt_id = f"int_{uuid4().hex[:12]}"
        envelope = InterruptEnvelope(
            interrupt_id=interrupt_id,
            session_id=session_id,
            run_id=request.run_id,
            kind=request.kind,
            prompt=request.prompt,
            title=request.title,
            description=request.description,
            severity=request.severity,
            confirm_label=request.confirm_label,
            cancel_label=request.cancel_label,
            options=request.options,
            fields=request.fields,
            context_artifact_ids=request.context_artifact_ids,
            default_value=request.default_value,
        )
        future: asyncio.Future[InterruptResponse] = asyncio.get_running_loop().create_future()
        self._pending_interrupts[interrupt_id] = (session_id, request.run_id or "", future, envelope)
        await self.publish_event(session_id, make_event("interrupt.requested", **envelope.model_dump()))
        return await future

    def list_pending_interrupts(self, session_id: str) -> list[dict]:
        items = []
        for interrupt_session_id, _run_id, _future, envelope in self._pending_interrupts.values():
            if interrupt_session_id == session_id:
                items.append(envelope.model_dump())
        return items

    async def resolve_interrupt(
        self,
        session_id: str,
        interrupt_id: str,
        response: InterruptResponse,
    ) -> InterruptResolvedResponse:
        pending = self._pending_interrupts.get(interrupt_id)
        if pending is None:
            raise KeyError(interrupt_id)
        pending_session_id, pending_run_id, future, _envelope = pending
        if pending_session_id != session_id:
            raise KeyError(interrupt_id)
        self._pending_interrupts.pop(interrupt_id, None)
        if not future.done():
            future.set_result(response)
        await self.publish_event(
            session_id,
            make_event(
                "interrupt.resolved",
                interrupt_id=interrupt_id,
                session_id=session_id,
                run_id=pending_run_id or None,
                value=response.value,
                kind=response.kind,
            ),
        )
        return InterruptResolvedResponse(status="resolved", session_id=session_id, interrupt_id=interrupt_id)

    async def respond_interrupt(
        self,
        session_id: str,
        interrupt_id: str,
        response: InterruptResponse,
    ) -> InterruptResolvedResponse:
        return await self.resolve_interrupt(session_id, interrupt_id, response)

    @classmethod
    def to_uploaded_artifact(cls, file_info: dict) -> Artifact:
        mime_type = str(file_info.get("mime_type") or "")
        artifact_type = "image" if mime_type.startswith("image/") else "file"
        if mime_type in {"text/markdown", "text/x-markdown"}:
            artifact_type = "report"
        return Artifact(
            artifact_id=str(file_info.get("file_id") or ""),
            type=artifact_type,
            title=str(file_info.get("filename") or file_info.get("file_id") or "file"),
            source="uploaded",
            path=file_info.get("path"),
            mime_type=file_info.get("mime_type"),
            preview_text=file_info.get("filename"),
            metadata={
                "size_bytes": file_info.get("size_bytes"),
                "runtime": cls.build_runtime_attachment(
                    str(file_info.get("filename") or ""),
                    str(file_info.get("mime_type") or ""),
                    str(file_info.get("path") or ""),
                ),
            },
        )

    async def _emit_artifact_created(self, session_id: str, artifact: Artifact) -> None:
        await self.publish_event(
            session_id,
            make_event("artifact.created", session_id=session_id, artifact=artifact.model_dump()),
        )

    async def save_upload(self, upload, session_id: str | None = None) -> FileUploadResponse:
        saved = await self.files.save(upload)
        artifact = self.to_uploaded_artifact(saved.model_dump())
        self._artifacts[artifact.artifact_id] = artifact
        if session_id:
            await self._emit_artifact_created(session_id, artifact)
        return FileUploadResponse(**saved.model_dump(), artifact=artifact)

    def get_artifact_preview(self, artifact_id: str) -> dict:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise KeyError(artifact_id)
        return resolve_artifact_preview(artifact)

    def preview_workspace_path(self, raw_path: str) -> dict:
        normalized = self._normalize_preview_reference(raw_path)
        candidate = Path(normalized)
        if not candidate.is_absolute() and ".." in candidate.parts:
            raise ValueError("Path outside workspace is not allowed")
        target = self._resolve_preview_target(normalized)
        if target is None:
            raise FileNotFoundError(normalized)
        suffix = target.suffix.lower()
        mime_type = mimetypes.guess_type(str(target))[0] or "text/plain"
        if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
            viewer_type = "image"
        elif suffix in {".md"}:
            viewer_type = "markdown"
        elif suffix in {".html", ".htm"}:
            viewer_type = "html"
        elif suffix in {".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".json", ".yaml", ".yml", ".sh", ".bat", ".ps1", ".toml", ".ini", ".sql", ".xml"}:
            viewer_type = "code"
        else:
            viewer_type = "text"
        relative_path = self._display_preview_path(target.resolve())
        payload = {
            "path": relative_path,
            "title": target.name,
            "mime_type": mime_type,
            "viewer_type": viewer_type,
        }
        if viewer_type == "image":
            payload["content_url"] = f"/workspace/file?path={relative_path}"
            return payload
        payload["content"] = target.read_text(encoding="utf-8", errors="replace")
        return payload

    @staticmethod
    def _normalize_preview_reference(raw_path: str) -> str:
        text = str(raw_path or "").strip().strip("`")
        text = text.replace("\\", "/")
        if "#L" in text:
            text = text.split("#L", 1)[0]
        if ":L" in text:
            text = text.split(":L", 1)[0]
        if "#" in text:
            text = text.split("#", 1)[0]
        if text.startswith("./"):
            text = text[2:]
        return text.strip()

    def _resolve_preview_target(self, normalized: str) -> Path | None:
        candidate = Path(normalized)
        if candidate.is_absolute():
            resolved = candidate.resolve()
            if self._is_under_allowed_roots(resolved) and resolved.exists() and resolved.is_file():
                return resolved
            return None
        relative = Path(normalized)
        if ".." in relative.parts:
            return None
        for root in self._preview_roots:
            direct = (root / relative).resolve()
            if self._is_under_allowed_roots(direct) and direct.exists() and direct.is_file():
                return direct
        if len(relative.parts) == 1:
            basename = relative.name
            matches: list[Path] = []
            for root in self._fallback_search_roots:
                for candidate_path in root.rglob(basename):
                    resolved = candidate_path.resolve()
                    if self._is_under_allowed_roots(resolved) and resolved.is_file():
                        matches.append(resolved)
            matches.sort(key=lambda p: (0 if 'memory' in p.parts else 1, len(p.parts), str(p)))
            if matches:
                return matches[0]
        return None

    def _is_under_allowed_roots(self, target: Path) -> bool:
        text = str(target)
        return any(text.startswith(str(root)) for root in self._preview_roots)

    def _display_preview_path(self, target: Path) -> str:
        for root in self._preview_roots:
            try:
                return target.relative_to(root).as_posix()
            except ValueError:
                continue
        return target.as_posix()

    # NOTE:
    # We intentionally avoid recursive fallback scans for preview resolution.
    # Deterministic direct path resolution keeps preview requests fast and
    # prevents blocking the event loop under high-volume inline link checks.

    def _ensure_event_queue(self, session_id: str) -> asyncio.Queue[dict]:
        if session_id not in self._event_queues:
            self._event_queues[session_id] = asyncio.Queue()
        return self._event_queues[session_id]

    @staticmethod
    def _session_summary(session_id: str, session: Session) -> SessionSummary:
        return SessionSummary(
            session_id=session_id,
            session_key=session.key,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )




