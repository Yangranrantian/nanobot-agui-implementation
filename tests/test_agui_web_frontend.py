from pathlib import Path


def test_agui_web_shell_exists_and_targets_session_api():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")

    index_html = (root / "index.html").read_text(encoding="utf-8")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert 'id="app"' in index_html
    assert "createSession" in app_js
    assert '"/sessions"' in app_js or "'/sessions'" in app_js


def test_agui_web_bootstrap_is_resilient_to_storage_failures():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "function readStoredApiBase()" in app_js
    assert "function renderFatalError(error)" in app_js
    assert "try {\n  bootstrap();\n} catch (error) {" in app_js


def test_agui_web_uses_custom_static_server_for_js_mime():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    package_json = (root / "package.json").read_text(encoding="utf-8")
    serve_py = (root / "serve.py").read_text(encoding="utf-8")

    assert "python serve.py --host 127.0.0.1 --port 4173" in package_json
    assert "'.js': 'text/javascript; charset=utf-8'" in serve_py


def test_agui_web_enter_sends_and_completion_sync():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "event.key === 'Enter' && !event.shiftKey" in app_js
    assert "void syncHistoryAfterCompletion(state.currentSessionId)" in app_js


def test_agui_web_status_visibility_controls():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "connection-chip" in app_js
    assert "setRunState('running')" in app_js
    assert "setSending(true)" in app_js


def test_agui_web_attachment_upload_and_send_state_feedback():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "file-status" in app_js
    assert "state.fileStatus = `Uploading ${files.length} file(s)...`" in app_js
    assert "state.attachments = [];" in app_js
    assert "attachments: sentAttachments" in app_js


def test_agui_web_multimodal_history_rendering_is_human_readable():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function normalizeMessageContent(content)" in app_js
    assert "item.type === 'image_url'" in app_js
    assert "function cleanImagePlaceholder(content, attachments)" in app_js
    assert "#file-input" in styles
    assert "display: none;" in styles
    assert 'id="file-input" type="file" multiple hidden' in app_js


def test_agui_web_renders_message_attachments_and_image_preview_modal():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "function filePreviewUrl(attachment)" in app_js
    assert "function openImageViewer(src, alt)" in app_js
    assert "id=\"image-viewer\"" in app_js
    assert "img.className = 'message-image'" in app_js


def test_agui_web_sessions_have_single_delete_current_action():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "delete-current-session" in app_js
    assert "void deleteSession();" in app_js
    assert "request(`/sessions/${sessionId}`, { method: 'DELETE' })" in app_js
    assert "overflow-y: scroll;" in styles


def test_agui_web_transcript_has_scrollbar_style():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert ".transcript::-webkit-scrollbar" in styles
    assert ".session-list::-webkit-scrollbar" in styles
    assert "scrollbar-gutter: stable" in styles


def test_agui_web_image_thumbnail_is_72px_default():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "width: 72px;" in styles
    assert "height: 72px;" in styles


def test_agui_web_right_pane_supports_inspector_and_preview_modes():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "rightPaneMode: 'inspector'" in app_js
    assert "previewArtifactId: null" in app_js
    assert 'id="right-pane"' in app_js
    assert "function openArtifactPreview(" in app_js
    assert "function closeArtifactPreview()" in app_js
    assert ".right-pane" in styles


def test_agui_web_renders_inline_collapsed_tool_execution_flow():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "case 'tool.started':" in app_js
    assert "function renderToolFlow(container)" in app_js
    assert "const details = document.createElement('details');" in app_js
    assert "details.open = false;" in app_js
    assert ".tool-flow" in styles
    assert ".tool-flow details" in styles


def test_agui_web_renders_clickable_blue_artifact_references():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function renderArtifactReference(" in app_js
    assert "artifact-reference" in app_js
    assert "openArtifactPreview(" in app_js
    assert "state.messages" in app_js
    assert ".artifact-reference" in styles
    assert "color: #2563eb" in styles


def test_agui_web_supports_mermaid_inline_render_and_copy_source():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function renderMermaidArtifact(" in app_js
    assert "Copy Source" in app_js
    assert "mermaid-preview-mode" in app_js
    assert ".mermaid-artifact" in styles


def test_agui_web_renders_inline_hitl_cards_and_result_summary():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "interrupt-card inline-hitl" in app_js
    assert "interrupt.kind === 'single_select'" in app_js
    assert "interrupt.kind === 'form'" in app_js
    assert "interrupt.resultSummary" in app_js
    assert "state.interrupts = state.interrupts.map(" in app_js
    assert ".inline-hitl" in styles


def test_agui_web_projects_task_events_into_inspector_status():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "case 'task.started':" in app_js
    assert "case 'task.completed':" in app_js
    assert "activeTaskCount" in app_js


def test_agui_web_inspector_is_minimal_and_details_collapsed():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "pane-section-title\">Artifacts" in app_js
    assert "pane-section-title\">Status" in app_js
    assert "pane-section-title\">Skills" in app_js
    assert "<details class=\"pane-details\"" in app_js
    assert "Tool logs are shown inline in transcript." in app_js
