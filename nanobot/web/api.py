from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse

from .events import encode_sse
from .interrupts import InterruptResolvedResponse, InterruptResponse
from .models import (
    CreateSessionRequest,
    FileUploadResponse,
    MessageListResponse,
    RunAcceptedResponse,
    SendMessageRequest,
    SessionListResponse,
    SessionSummary,
)
from .runtime import WebRuntime


def create_app(*, runtime: WebRuntime | None = None, workspace: Path | None = None) -> FastAPI:
    app = FastAPI(title="nanobot web runtime")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=['*'],
        allow_methods=['*'],
        allow_headers=['*'],
    )
    app.state.runtime = runtime or WebRuntime(workspace or Path.cwd())

    @app.post("/sessions", response_model=SessionSummary)
    def create_session(_payload: CreateSessionRequest) -> SessionSummary:
        return app.state.runtime.create_session()

    @app.get("/sessions", response_model=SessionListResponse)
    def list_sessions() -> SessionListResponse:
        return app.state.runtime.list_sessions()

    @app.delete("/sessions/{session_id}")
    def delete_session(session_id: str):
        try:
            return app.state.runtime.delete_session(session_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Session not found") from exc

    @app.get("/sessions/{session_id}/messages", response_model=MessageListResponse)
    def get_session_messages(session_id: str) -> MessageListResponse:
        return app.state.runtime.get_messages(session_id)

    @app.post("/sessions/{session_id}/messages", response_model=RunAcceptedResponse, status_code=202)
    async def send_message(session_id: str, payload: SendMessageRequest) -> RunAcceptedResponse:
        return await app.state.runtime.dispatch_message(
            session_id,
            payload.content,
            payload.attachments,
        )

    @app.get("/sessions/{session_id}/events")
    async def stream_session_events(session_id: str) -> StreamingResponse:
        async def _stream():
            async for event in app.state.runtime.stream_session_events(session_id):
                yield encode_sse(event)

        return StreamingResponse(_stream(), media_type="text/event-stream")

    @app.post("/sessions/{session_id}/interrupts/{interrupt_id}/respond", response_model=InterruptResolvedResponse)
    async def respond_interrupt(session_id: str, interrupt_id: str, payload: InterruptResponse) -> InterruptResolvedResponse:
        return await app.state.runtime.respond_interrupt(session_id, interrupt_id, payload)

    @app.post("/files", response_model=FileUploadResponse)
    async def upload_file(file: UploadFile = File(...), session_id: str | None = Query(default=None)) -> FileUploadResponse:
        return await app.state.runtime.save_upload(file, session_id=session_id)

    @app.get("/files/{file_id}")
    async def get_file(file_id: str):
        target = app.state.runtime.files.resolve(file_id)
        if target is None:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path=target)

    @app.get("/artifacts/{artifact_id}")
    async def get_artifact_preview(artifact_id: str):
        try:
            return app.state.runtime.get_artifact_preview(artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Artifact not found") from exc

    @app.get("/workspace/preview")
    async def preview_workspace_path(path: str = Query(...)):
        try:
            return app.state.runtime.preview_workspace_path(path)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/workspace/file")
    async def serve_workspace_file(path: str = Query(...)):
        try:
            target = app.state.runtime._resolve_preview_target(app.state.runtime._normalize_preview_reference(path))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if target is None:
            raise HTTPException(status_code=404, detail="File not found")
        return FileResponse(path=target)

    return app

