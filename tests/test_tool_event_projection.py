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
