import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse, ToolCallRequest
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

    async def fake_run(initial_messages, on_progress=None, on_event=None, emit_progress_text=True, **_kwargs):
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

    async def fake_run(initial_messages, on_progress=None, on_event=None, emit_progress_text=True, **_kwargs):
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





def test_interrupt_envelope_supports_anchor_message_id():
    from nanobot.web.interrupts import InterruptEnvelope

    envelope = InterruptEnvelope(
        interrupt_id="int_1",
        session_id="sess_1",
        kind="confirm",
        prompt="Approve command?",
        anchor_message_id="msg_1",
    )

    assert envelope.anchor_message_id == "msg_1"


def test_interrupt_request_supports_workflow_metadata_fields():
    request = InterruptRequest(
        kind="confirm",
        prompt="Approve command?",
        title="Execution confirmation",
        description="This command may modify files",
        severity="warning",
        confirm_label="Run command",
        cancel_label="Cancel",
        default_value=True,
        context_artifact_ids=["art_cmd"],
    )

    assert request.title == "Execution confirmation"
    assert request.severity == "warning"
    assert request.confirm_label == "Run command"
    assert request.cancel_label == "Cancel"
    assert request.default_value is True


def test_interrupt_request_supports_form_fields_and_select_options():
    request = InterruptRequest(
        kind="form",
        prompt="Need more info",
        title="Clarify parameters",
        options=[{"label": "Docs", "value": "docs"}],
        fields=[{"name": "filename", "type": "text", "required": True}],
    )

    assert request.title == "Clarify parameters"
    assert request.options == [{"label": "Docs", "value": "docs"}]
    assert request.fields == [{"name": "filename", "type": "text", "required": True}]


def test_interrupt_envelope_supports_run_id_and_custom_labels():
    from nanobot.web.interrupts import InterruptEnvelope

    envelope = InterruptEnvelope(
        interrupt_id="int_1",
        session_id="sess_1",
        run_id="run_1",
        kind="confirm",
        prompt="Approve command?",
        title="Execution confirmation",
        confirm_label="Continue",
        cancel_label="Stop",
    )

    assert envelope.run_id == "run_1"
    assert envelope.title == "Execution confirmation"
    assert envelope.confirm_label == "Continue"
    assert envelope.cancel_label == "Stop"


@pytest.mark.asyncio
async def test_runtime_tracks_pending_interrupt_by_session_run_and_id(tmp_path):
    loop = _make_loop(tmp_path)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    request = InterruptRequest(kind="confirm", prompt="Approve?", title="Confirm run", run_id="run_123")
    task = asyncio.create_task(runtime.handle_interrupt("web:sess_track", request))

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_track")
    assert len(pending) == 1
    assert pending[0]["run_id"] == "run_123"

    await runtime.resolve_interrupt("sess_track", pending[0]["interrupt_id"], InterruptResponse(kind="confirm", value=True))
    response = await task

    assert response.value is True
    assert runtime.list_pending_interrupts("sess_track") == []


@pytest.mark.asyncio
async def test_runtime_wrong_session_does_not_resume_pending_interrupt(tmp_path):
    loop = _make_loop(tmp_path)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    request = InterruptRequest(kind="confirm", prompt="Approve?", run_id="run_abc")
    task = asyncio.create_task(runtime.handle_interrupt("web:sess_a", request))

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_a")
    interrupt_id = pending[0]["interrupt_id"]

    with pytest.raises(KeyError):
        await runtime.resolve_interrupt("sess_b", interrupt_id, InterruptResponse(kind="confirm", value=False))

    assert not task.done()

    await runtime.resolve_interrupt("sess_a", interrupt_id, InterruptResponse(kind="confirm", value=True))
    response = await task
    assert response.value is True


@pytest.mark.asyncio
async def test_exec_tool_requires_confirmation_before_execution(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = AsyncMock(side_effect=[
        LLMResponse(
            content="Need to run a command",
            tool_calls=[ToolCallRequest(id="tc_exec", name="exec", arguments={"command": "echo hi"})],
        ),
        LLMResponse(content="command finished", tool_calls=[]),
    ])
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model", memory_window=10)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    execute_calls = []

    async def fake_execute(name, arguments):
        execute_calls.append((name, arguments))
        return "ok"

    loop.tools.execute = fake_execute

    task = asyncio.create_task(
        loop.process_direct("run the command", session_key="web:sess_exec", channel="web", chat_id="sess_exec")
    )

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_exec")

    assert len(pending) == 1
    assert pending[0]["kind"] == "confirm"
    assert pending[0]["title"] == "执行命令前确认"
    assert "需要先执行一条命令" in pending[0]["description"]
    assert pending[0]["confirm_label"] == "继续执行"
    assert pending[0]["cancel_label"] == "取消"
    assert execute_calls == []

    await runtime.resolve_interrupt("sess_exec", pending[0]["interrupt_id"], InterruptResponse(kind="confirm", value=True))
    result = await task

    assert result == "command finished"
    assert execute_calls == [("exec", {"command": "echo hi"})]


@pytest.mark.asyncio
async def test_rejected_exec_confirmation_prevents_tool_execution(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = AsyncMock(return_value=LLMResponse(
        content="Need to run a command",
        tool_calls=[ToolCallRequest(id="tc_exec", name="exec", arguments={"command": "echo hi"})],
    ))
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model", memory_window=10)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    execute_calls = []

    async def fake_execute(name, arguments):
        execute_calls.append((name, arguments))
        return "ok"

    loop.tools.execute = fake_execute

    task = asyncio.create_task(
        loop.process_direct("run the command", session_key="web:sess_exec_reject", channel="web", chat_id="sess_exec_reject")
    )

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_exec_reject")
    assert len(pending) == 1

    await runtime.resolve_interrupt("sess_exec_reject", pending[0]["interrupt_id"], InterruptResponse(kind="confirm", value=False))
    result = await task

    assert result == "操作已取消。"
    assert execute_calls == []


@pytest.mark.asyncio
async def test_overwrite_existing_file_requires_confirmation(tmp_path):
    existing = tmp_path / "notes.md"
    existing.write_text("old", encoding="utf-8")

    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = AsyncMock(side_effect=[
        LLMResponse(
            content="Need to overwrite file",
            tool_calls=[ToolCallRequest(id="tc_write", name="write_file", arguments={"path": str(existing), "content": "new"})],
        ),
        LLMResponse(content="write complete", tool_calls=[]),
    ])
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model", memory_window=10)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    execute_calls = []

    async def fake_execute(name, arguments):
        execute_calls.append((name, arguments))
        return "ok"

    loop.tools.execute = fake_execute

    task = asyncio.create_task(
        loop.process_direct("overwrite notes", session_key="web:sess_write", channel="web", chat_id="sess_write")
    )

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_write")
    assert len(pending) == 1
    assert pending[0]["kind"] == "confirm"
    assert pending[0]["title"] == "覆盖文件前确认"
    assert "目标文件已存在" in pending[0]["description"]
    assert pending[0]["confirm_label"] == "确认覆盖"
    assert pending[0]["cancel_label"] == "取消"
    assert execute_calls == []

    await runtime.resolve_interrupt("sess_write", pending[0]["interrupt_id"], InterruptResponse(kind="confirm", value=True))
    result = await task

    assert result == "write complete"
    assert execute_calls == [("write_file", {"path": str(existing), "content": "new"})]


@pytest.mark.asyncio
async def test_new_file_write_does_not_interrupt(tmp_path):
    target = tmp_path / "fresh.md"

    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = AsyncMock(side_effect=[
        LLMResponse(
            content="Create a file",
            tool_calls=[ToolCallRequest(id="tc_write", name="write_file", arguments={"path": str(target), "content": "hello"})],
        ),
        LLMResponse(content="write complete", tool_calls=[]),
    ])
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model", memory_window=10)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    execute_calls = []

    async def fake_execute(name, arguments):
        execute_calls.append((name, arguments))
        return "ok"

    loop.tools.execute = fake_execute

    result = await loop.process_direct("create file", session_key="web:sess_new_file", channel="web", chat_id="sess_new_file")

    assert runtime.list_pending_interrupts("sess_new_file") == []
    assert result == "write complete"
    assert execute_calls == [("write_file", {"path": str(target), "content": "hello"})]


@pytest.mark.asyncio
async def test_read_file_without_path_requests_single_select_and_resumes_with_choice(tmp_path):
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir(parents=True, exist_ok=True)

    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = AsyncMock(side_effect=[
        LLMResponse(
            content="Need a path",
            tool_calls=[ToolCallRequest(id="tc_read", name="read_file", arguments={})],
        ),
        LLMResponse(content="read complete", tool_calls=[]),
    ])
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model", memory_window=10)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    execute_calls = []

    async def fake_execute(name, arguments):
        execute_calls.append((name, arguments))
        return "content"

    loop.tools.execute = fake_execute

    task = asyncio.create_task(
        loop.process_direct("read something", session_key="web:sess_read_select", channel="web", chat_id="sess_read_select")
    )

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_read_select")
    assert len(pending) == 1
    assert pending[0]["kind"] == "single_select"
    assert pending[0]["title"] == "选择读取位置"
    assert len(pending[0]["options"]) >= 1

    selected = pending[0]["options"][0]["value"]
    await runtime.resolve_interrupt(
        "sess_read_select",
        pending[0]["interrupt_id"],
        InterruptResponse(kind="single_select", value=selected),
    )
    result = await task

    assert result == "read complete"
    assert execute_calls == [("read_file", {"path": selected})]


@pytest.mark.asyncio
async def test_write_file_without_path_requests_form_and_resumes_with_value(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    provider.chat = AsyncMock(side_effect=[
        LLMResponse(
            content="Need destination path",
            tool_calls=[ToolCallRequest(id="tc_write_form", name="write_file", arguments={"content": "hello"})],
        ),
        LLMResponse(content="write complete", tool_calls=[]),
    ])
    loop = AgentLoop(bus=MessageBus(), provider=provider, workspace=tmp_path, model="test-model", memory_window=10)
    runtime = WebRuntime(tmp_path, agent_loop=loop)

    execute_calls = []

    async def fake_execute(name, arguments):
        execute_calls.append((name, arguments))
        return "ok"

    loop.tools.execute = fake_execute

    task = asyncio.create_task(
        loop.process_direct("write something", session_key="web:sess_write_form", channel="web", chat_id="sess_write_form")
    )

    await asyncio.sleep(0)
    pending = runtime.list_pending_interrupts("sess_write_form")
    assert len(pending) == 1
    assert pending[0]["kind"] == "form"
    assert pending[0]["title"] == "补充文件路径"
    assert pending[0]["fields"] == [{"name": "path", "label": "文件路径", "type": "text", "required": True}]

    await runtime.resolve_interrupt(
        "sess_write_form",
        pending[0]["interrupt_id"],
        InterruptResponse(kind="form", value={"path": "notes/generated.md"}),
    )
    result = await task

    assert result == "write complete"
    assert execute_calls == [("write_file", {"content": "hello", "path": "notes/generated.md"})]
