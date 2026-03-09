from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InterruptRequest(BaseModel):
    kind: str
    prompt: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    fields: list[dict[str, Any]] = Field(default_factory=list)


class InterruptEnvelope(InterruptRequest):
    interrupt_id: str
    session_id: str


class InterruptResponse(BaseModel):
    kind: str
    value: Any


class InterruptResolvedResponse(BaseModel):
    status: str
    session_id: str
    interrupt_id: str
