import pytest

from nanobot.providers.litellm_provider import LiteLLMProvider


def test_litellm_provider_keeps_unprefixed_glm_model_for_zhipu_openai_compatible_base():
    provider = LiteLLMProvider(
        api_key="test",
        api_base="https://open.bigmodel.cn/api/coding/paas/v4",
        default_model="glm-5",
        provider_name="zhipu",
    )

    assert provider._resolve_model("glm-4.6v") == "glm-4.6v"
    assert provider._resolve_model("zai/glm-4.6v") == "glm-4.6v"


def test_litellm_provider_still_prefixes_glm_without_zhipu_provider_context():
    provider = LiteLLMProvider(default_model="glm-5")

    assert provider._resolve_model("glm-4.6v") == "zai/glm-4.6v"


def test_litellm_provider_normalizes_zhipu_data_url_blocks_to_base64_url():
    provider = LiteLLMProvider(
        api_key="test",
        api_base="https://open.bigmodel.cn/api/coding/paas/v4",
        default_model="glm-5",
        provider_name="zhipu",
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "what is in this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJDRA=="}},
            ],
        }
    ]

    normalized = provider._normalize_zhipu_multimodal_messages(messages)

    assert normalized[0]["content"][1]["image_url"]["url"] == "QUJDRA=="


def test_litellm_provider_keeps_data_url_for_non_zhipu_provider():
    provider = LiteLLMProvider(
        api_key="test",
        api_base="https://api.openai.com/v1",
        default_model="gpt-4o-mini",
        provider_name="openai",
    )
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "what is in this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,QUJDRA=="}},
            ],
        }
    ]

    normalized = provider._normalize_zhipu_multimodal_messages(messages)

    assert normalized[0]["content"][1]["image_url"]["url"] == "data:image/png;base64,QUJDRA=="


@pytest.mark.asyncio
async def test_litellm_provider_sets_custom_llm_provider_for_unprefixed_zhipu_models(monkeypatch):
    captured = {}

    class _Msg:
        content = "ok"
        tool_calls = []

    class _Choice:
        message = _Msg()
        finish_reason = "stop"

    class _Resp:
        choices = [_Choice()]
        usage = None

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _Resp()

    monkeypatch.setattr("nanobot.providers.litellm_provider.acompletion", fake_acompletion)

    provider = LiteLLMProvider(
        api_key="test",
        api_base="https://open.bigmodel.cn/api/coding/paas/v4",
        default_model="glm-5",
        provider_name="zhipu",
    )

    await provider.chat(messages=[{"role": "user", "content": "hi"}], model="glm-4.6v")

    assert captured["model"] == "glm-4.6v"
    assert captured["custom_llm_provider"] == "openai"



def test_litellm_provider_parse_uses_reasoning_content_as_fallback_for_zhipu():
    provider = LiteLLMProvider(
        api_key="test",
        api_base="https://open.bigmodel.cn/api/coding/paas/v4",
        default_model="glm-4.6v",
        provider_name="zhipu",
    )

    class _Message:
        content = ""
        tool_calls = []
        reasoning_content = "final answer"
        thinking_blocks = None

    class _Choice:
        message = _Message()
        finish_reason = "stop"

    class _Response:
        choices = [_Choice()]
        usage = None

    parsed = provider._parse_response(_Response())

    assert parsed.content == "final answer"
