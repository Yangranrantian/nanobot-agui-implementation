from __future__ import annotations

import inspect
import json
from typing import Any, Awaitable, Callable

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


def make_event(event_type: str, **payload: Any) -> dict[str, Any]:
    return {"type": event_type, **payload}


async def emit_event(callback: EventCallback | None, event: dict[str, Any]) -> None:
    if callback is None:
        return
    result = callback(event)
    if inspect.isawaitable(result):
        await result


def encode_sse(event: dict[str, Any]) -> str:
    event_type = event.get("type", "message")
    return f"event: {event_type}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
