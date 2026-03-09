from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from .models import AgentEvent

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


def make_event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, **payload}


def make_event_v2(
    event_type: str,
    *,
    session_id: str,
    run_id: str,
    payload: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    event = AgentEvent(
        type=event_type,
        session_id=session_id,
        run_id=run_id,
        timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
        payload=payload or {},
    )
    return event.model_dump()


async def emit_event(callback: EventCallback | None, event: dict[str, Any]) -> None:
    if callback is None:
        return
    result = callback(event)
    if inspect.isawaitable(result):
        await result


def encode_sse(event: dict[str, Any]) -> str:
    event_type = event.get("type", "message")
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
