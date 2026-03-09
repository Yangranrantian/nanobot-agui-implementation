from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    metadata: dict[str, str] = Field(default_factory=dict)


class SessionSummary(BaseModel):
    session_id: str
    session_key: str
    created_at: datetime | str
    updated_at: datetime | str


class SessionListResponse(BaseModel):
    items: list[SessionSummary]


class MessageRecord(BaseModel):
    role: str
    content: str | list | None = None
    timestamp: str | None = None


class MessageListResponse(BaseModel):
    items: list[MessageRecord]


class SendMessageRequest(BaseModel):
    content: str
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class RunAcceptedResponse(BaseModel):
    run_id: str
    session_id: str
    status: str


class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    mime_type: str
    size_bytes: int
    path: str
