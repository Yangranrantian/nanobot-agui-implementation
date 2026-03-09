import asyncio
from unittest.mock import MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse
from nanobot.web.interrupts import InterruptRequest, InterruptResponse
from nanobot.web.runtime import WebRuntime


def _make_loop(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = MagicMock(return_value=LLMResponse(content="unused", tool_calls=[]))
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        memory_window=10,
    )


@pytest.mark.asyncio
async def test_agent_loop_can_request_interrupt_and_wait(tmp_path):
    loop = _make_loop(tmp_path)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    async def fake_run(initial_messages, on_progress=None, on_event=None):
        response = await loop.request_interrupt(
            "web:sess_interrupt",
            InterruptRequest(kind="confirm", prompt="Approve?"),
            on_event=on_event,
        )
        content = "approved path" if response.value is True else "rejected path"
        return content, [], [
            *initial_messages,
            {"role": "assistant", "content": content},
        ]

    loop._run_agent_loop = fake_run

    task = asyncio.create_task(
        loop.process_direct(
            "needs approval",
            session_key="web:sess_interrupt",
            channel="web",
            chat_id="sess_interrupt",
        )
    )

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_interrupt")
    assert len(pending) == 1

    interrupt_id = pending[0]["interrupt_id"]
    await runtime.resolve_interrupt(
        "sess_interrupt",
        interrupt_id,
        InterruptResponse(kind="confirm", value=True),
    )

    result = await task
    assert result == "approved path"


def test_interrupt_response_resumes_run():
    from fastapi.testclient import TestClient
    from nanobot.web.api import create_app

    class FakeInterruptRuntime:
        async def respond_interrupt(self, session_id, interrupt_id, response):
            return {"status": "resolved", "session_id": session_id, "interrupt_id": interrupt_id}

    client = TestClient(create_app(runtime=FakeInterruptRuntime()))
    response = client.post(
        "/sessions/sess_123/interrupts/int_001/respond",
        json={"kind": "confirm", "value": True},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_dispatch_message_persists_history_for_runtime_reader(tmp_path):
    loop = _make_loop(tmp_path)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    async def fake_run(initial_messages, on_progress=None, on_event=None):
        return "saved reply", [], [
            *initial_messages,
            {"role": "assistant", "content": "saved reply"},
        ]

    loop._run_agent_loop = fake_run

    session = runtime.create_session()
    await runtime.dispatch_message(session.session_id, "persist me", [])
    await asyncio.sleep(0.1)

    history = runtime.get_messages(session.session_id)

    assert [item.role for item in history.items] == ["user", "assistant"]
    assert [item.content for item in history.items] == ["persist me", "saved reply"]


@pytest.mark.asyncio
async def test_web_runtime_dispatch_passes_attachment_paths_to_agent_loop(tmp_path):
    class CaptureLoop:
        def __init__(self):
            self.calls = []

        async def process_direct(self, content, **kwargs):
            self.calls.append({"content": content, **kwargs})
            return "ok"

        def set_interrupt_handler(self, _handler):
            return None

    loop = CaptureLoop()
    runtime = WebRuntime(tmp_path, agent_loop=loop)
    session = runtime.create_session()

    attachments = [
        {"filename": "a.png", "path": str(tmp_path / "uploads" / "a.png")},
        {"filename": "note.txt", "path": str(tmp_path / "uploads" / "note.txt")},
    ]

    await runtime.dispatch_message(session.session_id, "what is in the image", attachments)
    await asyncio.sleep(0.05)

    assert len(loop.calls) == 1
    call = loop.calls[0]
    assert call["media"] == [item["path"] for item in attachments]
    assert call["metadata"]["attachments"] == attachments
