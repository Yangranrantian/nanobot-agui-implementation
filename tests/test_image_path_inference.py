from pathlib import Path


def test_infer_image_paths_from_text_supports_relative_and_absolute(tmp_path):
    from nanobot.agent.loop import AgentLoop

    rel = tmp_path / "a.png"
    rel.write_bytes(b"\x89PNG\r\n\x1a\n")
    abs_img = tmp_path / "nested" / "b.jpg"
    abs_img.parent.mkdir(parents=True, exist_ok=True)
    abs_img.write_bytes(b"\xff\xd8\xff")

    text = f"请看 a.png 和 {abs_img.as_posix()} 这两张图"
    got = AgentLoop.infer_image_paths_from_text(text, tmp_path)

    assert str(rel.resolve()) in got
    assert str(abs_img.resolve()) in got


def test_infer_image_paths_from_text_ignores_non_image_paths(tmp_path):
    from nanobot.agent.loop import AgentLoop

    (tmp_path / "note.md").write_text("x", encoding="utf-8")
    got = AgentLoop.infer_image_paths_from_text("查看 note.md 和 /铜色系", tmp_path)
    assert got == []


def test_infer_image_paths_from_text_handles_filename_without_space_boundary(tmp_path):
    from nanobot.agent.loop import AgentLoop

    img = tmp_path / "儿.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    got = AgentLoop.infer_image_paths_from_text("儿.png这个图片描述了什么", tmp_path)
    assert str(img.resolve()) in got
