from pathlib import Path

import pytest

from nanobot.agent.tools.image import ImageInspectTool
from nanobot.providers.base import LLMResponse


class _FakeProvider:
    def __init__(self):
        self.last_messages = None
        self.called_models = []

    async def chat(self, **kwargs):
        self.last_messages = kwargs.get("messages")
        self.called_models.append(kwargs.get("model"))
        return LLMResponse(content="图中是一只猫。")


@pytest.mark.asyncio
async def test_image_inspect_tool_builds_multimodal_message(tmp_path: Path):
    image = tmp_path / "cat.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    provider = _FakeProvider()
    tool = ImageInspectTool(provider=provider, workspace=tmp_path, model_getter=lambda: "openai/gpt-4o-mini")

    result = await tool.execute(path="cat.png", question="这张图里有什么？")

    assert "猫" in result
    assert provider.last_messages is not None
    user_content = provider.last_messages[0]["content"]
    assert user_content[0]["type"] == "text"
    assert "这张图里有什么" in user_content[0]["text"]
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.asyncio
async def test_image_inspect_tool_rejects_non_image_file(tmp_path: Path):
    note = tmp_path / "note.md"
    note.write_text("# hello", encoding="utf-8")
    provider = _FakeProvider()
    tool = ImageInspectTool(provider=provider, workspace=tmp_path, model_getter=lambda: "openai/gpt-4o-mini")

    result = await tool.execute(path="note.md", question="总结内容")

    assert "not an image" in result.lower()


class _FallbackProvider:
    def __init__(self):
        self.called_models = []

    async def chat(self, **kwargs):
        model = kwargs.get("model")
        self.called_models.append(model)
        if model == "glm-5":
            return LLMResponse(content="Error calling LLM: litellm.BadRequestError: OpenAIException - API 调用参数有误，请检查文档。")
        return LLMResponse(content="这是一张人物照片。")


@pytest.mark.asyncio
async def test_image_inspect_tool_retries_with_image_model_when_primary_fails(tmp_path: Path):
    image = tmp_path / "儿.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    provider = _FallbackProvider()
    tool = ImageInspectTool(
        provider=provider,
        workspace=tmp_path,
        model_getter=lambda: "glm-5",
        image_model_getter=lambda: "glm-4.6v",
    )

    result = await tool.execute(path="儿.png", question="描述这张图片")

    assert "人物照片" in result
    assert provider.called_models == ["glm-5", "glm-4.6v"]
