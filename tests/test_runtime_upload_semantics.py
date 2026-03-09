from nanobot.web.runtime import WebRuntime


def test_non_image_uploads_are_referenced_by_path_for_runtime(tmp_path):
    runtime = WebRuntime(tmp_path)
    resolved = runtime.build_runtime_attachment("notes.txt", "text/plain", str(tmp_path / "notes.txt"))
    assert resolved["mode"] == "path"


def test_image_uploads_keep_multimodal_runtime_mode(tmp_path):
    runtime = WebRuntime(tmp_path)
    resolved = runtime.build_runtime_attachment("image.png", "image/png", str(tmp_path / "image.png"))
    assert resolved["mode"] == "image"
