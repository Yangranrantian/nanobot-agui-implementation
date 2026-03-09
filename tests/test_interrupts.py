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
    attachment = {
        "file_id": "file_123",
        "filename": "a.png",
        "mime_type": "image/png",
        "path": str(tmp_path / "a.png"),
    }
    await runtime.dispatch_message(session.session_id, "persist me", [attachment])
    await asyncio.sleep(0.1)

    history = runtime.get_messages(session.session_id)

    assert [item.role for item in history.items] == ["user", "assistant"]
    assert [item.content for item in history.items] == ["persist me", "saved reply"]
    assert history.items[0].attachments == [attachment]


@pytest.mark.asyncio
async def test_web_runtime_dispatch_passes_only_image_attachment_paths_to_agent_loop(tmp_path):
    class CaptureLoop:
        def __init__(self):
            self.calls = []
            self.model = "zhipu/glm-5"
            self.provider = type("P", (), {"api_base": "https://open.bigmodel.cn/api/coding/paas/v4"})()

        async def process_direct(self, content, **kwargs):
            self.calls.append({"content": content, **kwargs})
            return "ok"

        def set_interrupt_handler(self, _handler):
            return None

    loop = CaptureLoop()
    runtime = WebRuntime(tmp_path, agent_loop=loop, provider_name="openai")
    session = runtime.create_session()

    attachments = [
        {"filename": "a.png", "mime_type": "image/png", "path": str(tmp_path / "uploads" / "a.png")},
        {"filename": "note.txt", "mime_type": "text/plain", "path": str(tmp_path / "uploads" / "note.txt")},
    ]

    await runtime.dispatch_message(session.session_id, "what is in the image", attachments)
    await asyncio.sleep(0.05)

    assert len(loop.calls) == 1
    call = loop.calls[0]
    assert call["media"] == [attachments[0]["path"]]
    assert call["metadata"]["attachments"] == attachments


def test_web_runtime_uses_configured_image_model_primary_for_non_vision_model(tmp_path):
    runtime = WebRuntime(
        tmp_path,
        image_model_primary="openai/gpt-5-mini",
        provider_name="openai",
    )

    assert runtime._pick_multimodal_model("openai/gpt-5") == "openai/gpt-5-mini"


def test_web_runtime_uses_provider_fallback_when_image_model_primary_missing(tmp_path):
    runtime = WebRuntime(tmp_path, provider_name="anthropic")

    assert runtime._pick_multimodal_model("anthropic/claude-sonnet-4-5") == "anthropic/claude-opus-4-6"


def test_web_runtime_normalizes_zhipu_prefix_to_unprefixed_model_for_multimodal(tmp_path):
    runtime = WebRuntime(tmp_path, provider_name="zhipu")

    assert runtime._pick_multimodal_model("zhipu/glm-4.6v") == "glm-4.6v"


@pytest.mark.asyncio
async def test_web_runtime_allows_zhipu_local_image_upload_to_reach_agent_loop(tmp_path):
    class CaptureLoop:
        def __init__(self):
            self.model = "zhipu/glm-5"
            self.calls = 0
            self.last_media = None
            self.provider = type("P", (), {"api_base": "https://open.bigmodel.cn/api/coding/paas/v4"})()

        async def process_direct(self, _content, **kwargs):
            self.calls += 1
            self.last_media = kwargs.get("media")
            return "ok"

        def set_interrupt_handler(self, _handler):
            return None

    loop = CaptureLoop()
    runtime = WebRuntime(tmp_path, agent_loop=loop, provider_name="zhipu")
    session = runtime.create_session()

    attachment = {"filename": "a.png", "mime_type": "image/png", "path": str(tmp_path / "a.png")}
    await runtime.dispatch_message(session.session_id, "what is this image", [attachment])
    await asyncio.sleep(0.05)

    assert loop.calls == 1
    assert loop.last_media == [attachment["path"]]


@pytest.mark.asyncio
async def test_web_runtime_clamps_zhipu_vision_max_tokens_and_restores_after_run(tmp_path):
    class CaptureLoop:
        def __init__(self):
            self.model = "zhipu/glm-5"
            self.max_tokens = 131072
            self.seen_max_tokens = None
            self.provider = type("P", (), {"api_base": "https://open.bigmodel.cn/api/coding/paas/v4"})()

        async def process_direct(self, _content, **_kwargs):
            self.seen_max_tokens = self.max_tokens
            return "ok"

        def set_interrupt_handler(self, _handler):
            return None

    loop = CaptureLoop()
    runtime = WebRuntime(tmp_path, agent_loop=loop, provider_name="zhipu")
    session = runtime.create_session()

    attachment = {"filename": "a.png", "mime_type": "image/png", "path": str(tmp_path / "a.png")}
    await runtime.dispatch_message(session.session_id, "what is this image", [attachment])
    await asyncio.sleep(0.05)

    assert loop.seen_max_tokens == 16384
    assert loop.max_tokens == 131072

@pytest.mark.asyncio
async def test_web_runtime_reports_actionable_error_for_zhipu_local_image_upload(tmp_path):
    class FailingLoop:
        def __init__(self):
            self.model = "glm-4.6v"
            self.provider = type("P", (), {"api_base": "https://open.bigmodel.cn/api/coding/paas/v4"})()

        async def process_direct(self, *_args, **_kwargs):
            raise RuntimeError("litellm.BadRequestError: ZaiException - image payload parsing error")

        def set_interrupt_handler(self, _handler):
            return None

    runtime = WebRuntime(tmp_path, agent_loop=FailingLoop(), provider_name="zhipu")
    session = runtime.create_session()

    await runtime.dispatch_message(
        session.session_id,
        "what is in image",
        [{"filename": "a.png", "mime_type": "image/png", "path": str(tmp_path / "a.png")}],
    )

    queue = runtime._ensure_event_queue(session.session_id)
    error_event = None
    for _ in range(5):
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        if event.get("type") == "error":
            error_event = event
            break

    assert error_event is not None
    assert "size <= 5MB" in error_event.get("message", "")


def test_interrupt_request_supports_single_select_form_and_artifact_context():
    request = InterruptRequest(
        kind="single_select",
        prompt="Pick one option",
        options=[{"id": "a", "label": "Option A"}],
        fields=[{"name": "reason", "type": "text"}],
        description="Need your decision",
        context_artifact_ids=["art_1"],
    )

    assert request.kind == "single_select"
    assert request.description == "Need your decision"
    assert request.context_artifact_ids == ["art_1"]




