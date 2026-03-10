import asyncio

from nanobot.web.runtime import WebRuntime


class _FakeAgentLoop:
    def __init__(self):
        self.model = "openai/gpt-5-mini"
        self.max_tokens = 4096
        self.last_media = None

    async def process_direct(self, content, **kwargs):
        self.last_media = kwargs.get("media")
        return "ok"


def test_web_runtime_does_not_auto_infer_image_paths_from_plain_text(tmp_path):
    fake = _FakeAgentLoop()
    runtime = WebRuntime(tmp_path, agent_loop=fake)

    asyncio.run(runtime._run_agent("sess_1", "儿.png这个图片描述了什么", [], "run_1"))
    assert fake.last_media == []


def test_web_runtime_keeps_uploaded_image_attachments_as_media(tmp_path):
    image = tmp_path / "儿.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    fake = _FakeAgentLoop()
    runtime = WebRuntime(tmp_path, agent_loop=fake)
    attachments = [{"filename": "儿.png", "mime_type": "image/png", "path": str(image.resolve())}]

    asyncio.run(runtime._run_agent("sess_1", "请描述这张图", attachments, "run_1"))
    assert fake.last_media is not None
    assert str(image.resolve()) in fake.last_media
