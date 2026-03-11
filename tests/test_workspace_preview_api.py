from pathlib import Path
from fastapi.testclient import TestClient


def test_workspace_preview_endpoint_returns_text_content(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    target = tmp_path / "notes" / "readme.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# hello\nworld", encoding="utf-8")

    app = create_app(runtime=WebRuntime(tmp_path))
    client = TestClient(app)

    resp = client.get("/workspace/preview", params={"path": "notes/readme.md"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["path"] == "notes/readme.md"
    assert body["content"].startswith("# hello")
    assert body["viewer_type"] == "markdown"


def test_workspace_preview_endpoint_rejects_path_outside_workspace(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    app = create_app(runtime=WebRuntime(tmp_path))
    client = TestClient(app)

    resp = client.get("/workspace/preview", params={"path": "../secret.txt"})
    assert resp.status_code == 400


def test_workspace_preview_endpoint_accepts_allowed_absolute_preview_root(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    ext_root = tmp_path / "external-preview"
    ext_root.mkdir(parents=True, exist_ok=True)
    target = ext_root / "AGENTS.md"
    target.write_text("# agent rules", encoding="utf-8")

    app = create_app(runtime=WebRuntime(tmp_path, preview_roots=[tmp_path, ext_root]))
    client = TestClient(app)

    resp = client.get("/workspace/preview", params={"path": str(target)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "AGENTS.md"
    assert "agent rules" in body["content"]


def test_runtime_default_preview_roots_include_home_directory(tmp_path):
    from pathlib import Path
    from nanobot.web.runtime import WebRuntime

    runtime = WebRuntime(tmp_path)
    roots = {str(p) for p in runtime._preview_roots}
    assert str(Path.home().resolve()) in roots


def test_workspace_preview_endpoint_can_resolve_basename_from_memory_dir(tmp_path):
    from nanobot.web.api import create_app
    from nanobot.web.runtime import WebRuntime

    target = tmp_path / "memory" / "HISTORY.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# history", encoding="utf-8")

    app = create_app(runtime=WebRuntime(tmp_path))
    client = TestClient(app)

    resp = client.get("/workspace/preview", params={"path": "HISTORY.md"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "HISTORY.md"
    assert body["path"] == "memory/HISTORY.md"


def test_agui_frontend_prefers_full_path_variant_over_bare_filename():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "const matches = [];" in app_js
    assert "matches.sort((a, b) => {" in app_js
    assert "return b.variant.length - a.variant.length;" in app_js
