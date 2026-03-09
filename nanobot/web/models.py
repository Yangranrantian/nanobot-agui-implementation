from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class InterruptCardState(BaseModel):
    interrupt_id: str
    kind: str
    state: str = "pending"
    result_summary: str | None = None


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
    artifact: "Artifact | None" = None


class AgentEvent(BaseModel):
    type: str
    session_id: str
    run_id: str
    timestamp: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value == "error":
            return value
        families = ("message.", "tool.", "artifact.", "task.", "interrupt.")
        if value.startswith(families):
            return value
        raise ValueError("Unsupported event type family for Event Model v2")


class Artifact(BaseModel):
    artifact_id: str
    type: str
    title: str
    source: str
    path: str | None = None
    url: str | None = None
    mime_type: str | None = None
    preview_text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        allowed = {"file", "code", "image", "link", "diagram", "report"}
        if value not in allowed:
            raise ValueError("Unsupported artifact type")
        return value

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        allowed = {"uploaded", "generated", "workspace", "linked"}
        if value not in allowed:
            raise ValueError("Unsupported artifact source")
        return value

