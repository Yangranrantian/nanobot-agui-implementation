from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

from nanobot.session.manager import Session, SessionManager

from .events import make_event
from .files import FileStore
from .interrupts import InterruptEnvelope, InterruptRequest, InterruptResolvedResponse, InterruptResponse
from .models import (
    FileUploadResponse,
    MessageListResponse,
    MessageRecord,
    RunAcceptedResponse,
    SessionListResponse,
    SessionSummary,
)


class WebRuntime:
    """Thin adapter that exposes browser-facing session operations."""

    def __init__(self, workspace: Path, agent_loop=None):
        self.workspace = Path(workspace)
        self.sessions = SessionManager(self.workspace)
        self.agent_loop = None
        self._event_queues: dict[str, asyncio.Queue[dict]] = {}
        self._pending_interrupts: dict[str, tuple[str, asyncio.Future[InterruptResponse], InterruptEnvelope]] = {}
        self.files = FileStore(self.workspace / "web_uploads")
        if agent_loop is not None:
            self.attach_agent_loop(agent_loop)

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

    def get_messages(self, session_id: str) -> MessageListResponse:
        key = self.session_key(session_id)
        self.sessions.invalidate(key)
        session = self.sessions.get_or_create(key)
        items = [
            MessageRecord(
                role=message.get("role", "assistant"),
                content=message.get("content"),
                timestamp=message.get("timestamp"),
            )
            for message in session.get_history()
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
        media_paths = [item.get("path") for item in attachments if item.get("path")]
        try:
            await self.agent_loop.process_direct(
                content,
                session_key=self.session_key(session_id),
                channel="web",
                chat_id=session_id,
                media=media_paths,
                metadata={"attachments": attachments},
                on_event=lambda event: self.publish_event(session_id, {**event, "run_id": event.get("run_id", run_id)}),
            )
        except Exception as exc:
            message = str(exc)
            lower = message.lower()
            if media_paths and ("badrequest" in lower or "image" in lower or "vision" in lower):
                message = "Current model does not accept image inputs. Please switch to a vision-capable model and retry."
            await self.publish_event(
                session_id,
                make_event("error", run_id=run_id, session_id=session_id, message=message),
            )

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
            kind=request.kind,
            prompt=request.prompt,
            options=request.options,
            fields=request.fields,
        )
        future: asyncio.Future[InterruptResponse] = asyncio.get_running_loop().create_future()
        self._pending_interrupts[interrupt_id] = (session_id, future, envelope)
        await self.publish_event(session_id, make_event("interrupt.requested", **envelope.model_dump()))
        return await future

    def list_pending_interrupts(self, session_id: str) -> list[dict]:
        items = []
        for interrupt_session_id, _future, envelope in self._pending_interrupts.values():
            if interrupt_session_id == session_id:
                items.append(envelope.model_dump())
        return items

    async def resolve_interrupt(
        self,
        session_id: str,
        interrupt_id: str,
        response: InterruptResponse,
    ) -> InterruptResolvedResponse:
        pending = self._pending_interrupts.pop(interrupt_id)
        pending_session_id, future, envelope = pending
        if pending_session_id != session_id:
            raise KeyError(interrupt_id)
        if not future.done():
            future.set_result(response)
        await self.publish_event(
            session_id,
            make_event("interrupt.resolved", interrupt_id=interrupt_id, session_id=session_id, value=response.value, kind=response.kind),
        )
        return InterruptResolvedResponse(status="resolved", session_id=session_id, interrupt_id=interrupt_id)

    async def respond_interrupt(
        self,
        session_id: str,
        interrupt_id: str,
        response: InterruptResponse,
    ) -> InterruptResolvedResponse:
        return await self.resolve_interrupt(session_id, interrupt_id, response)

    async def save_upload(self, upload) -> FileUploadResponse:
        saved = await self.files.save(upload)
        return FileUploadResponse(**saved.model_dump())

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
