from unittest.mock import AsyncMock, MagicMock

import pytest

from nanobot.agent.loop import AgentLoop
from nanobot.bus.queue import MessageBus
from nanobot.providers.base import LLMResponse


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
async def test_agent_loop_emits_run_and_message_events(tmp_path):
    loop = _make_loop(tmp_path)
    loop.provider.chat = AsyncMock(return_value=LLMResponse(content="hello back", tool_calls=[]))
    loop.tools.get_definitions = MagicMock(return_value=[])

    events = []

    await loop.process_direct("hello", on_event=events.append)

    assert any(event["type"] == "run.started" for event in events)
    assert any(event["type"] == "message.completed" for event in events)
