from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse, ToolCallRequest


def _make_loop(tmp_path):
    provider = MagicMock()
    provider.get_default_model.return_value = "test-model"
    return AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        memory_window=10,
    )


@pytest.mark.asyncio
async def test_tool_events_include_summary_and_preview_fields(tmp_path):
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="tool_1", name="list_dir", arguments={})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.get_definitions = MagicMock(return_value=[])

    events = []
    await loop.process_direct("read a file", on_event=events.append)
    tool_events = [e for e in events if e["type"].startswith("tool.")]

    assert tool_events
    assert "summary" in tool_events[0]["payload"]


@pytest.mark.asyncio
async def test_file_tool_events_emit_explicit_artifact_reference(tmp_path):
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="tool_1", name="write_file", arguments={"path": "notes.md", "content": "hello"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.get_definitions = MagicMock(return_value=[])

    events = []
    await loop.process_direct("create notes", on_event=events.append)

    completed = next(event for event in events if event["type"] == "tool.completed")
    artifact_event = next(event for event in events if event["type"] in {"artifact.created", "artifact.referenced"})

    assert completed["payload"]["linked_artifact_ids"]
    assert artifact_event["artifact"]["title"] == "notes.md"
    assert artifact_event["artifact"]["path"].endswith("notes.md")


@pytest.mark.asyncio
async def test_image_inspect_tool_emits_image_artifact_reference(tmp_path):
    loop = _make_loop(tmp_path)
    image_path = tmp_path / "202505012239.png"
    image_path.write_bytes(b"fake")
    loop.provider.chat = AsyncMock(
        side_effect=[
            LLMResponse(
                content="",
                tool_calls=[ToolCallRequest(id="tool_1", name="image_inspect", arguments={"path": str(image_path), "question": "what is this"})],
            ),
            LLMResponse(content="done", tool_calls=[]),
        ]
    )
    loop.tools.get_definitions = MagicMock(return_value=[])
    loop.tools.execute = AsyncMock(return_value="a gym photo")

    events = []
    await loop.process_direct("describe image", on_event=events.append)

    artifact_event = next(event for event in events if event["type"] == "artifact.referenced")
    assert artifact_event["artifact"]["type"] == "image"
    assert artifact_event["artifact"]["path"].endswith("202505012239.png")
