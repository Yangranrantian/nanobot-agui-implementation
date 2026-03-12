from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InterruptRequest(BaseModel):
    kind: str
    prompt: str
    run_id: str | None = None
    title: str | None = None
    description: str | None = None
    severity: str = "info"
    confirm_label: str | None = None
    cancel_label: str | None = None
    options: list[dict[str, Any]] = Field(default_factory=list)
    fields: list[dict[str, Any]] = Field(default_factory=list)
    context_artifact_ids: list[str] = Field(default_factory=list)
    default_value: Any | None = None


class InterruptEnvelope(InterruptRequest):
    interrupt_id: str
    session_id: str
    run_id: str | None = None
    anchor_message_id: str | None = None


class InterruptResponse(BaseModel):
    kind: str
    value: Any


class InterruptResolvedResponse(BaseModel):
    status: str
    session_id: str
    interrupt_id: str
