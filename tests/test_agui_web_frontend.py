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
    assert "state.fileStatus = `正在上传 ${files.length} 个文件...`" in app_js
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
    assert "copy-mermaid-source" in app_js
    assert "block.addEventListener('click'" in app_js
    assert "mermaid-open" not in app_js
    assert "mermaid-copy" not in app_js
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

    assert "pane-section-title\">对象" in app_js
    assert "pane-section-title\">状态" in app_js
    assert "pane-section-title\">技能" in app_js
    assert "<details class=\"pane-details\"" in app_js
    assert "模式：" in app_js


def test_agui_web_tool_flow_is_bound_to_assistant_message_position():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "function getActiveAssistantMessage()" in app_js
    assert "function ensurePendingAssistantMessage()" in app_js
    assert "renderToolFlow(toolStage, message);" in app_js
    assert "state.messages.push(pendingMessage);" in app_js
    assert "active.toolFlow = active.toolFlow || [];" in app_js
    assert "status: 'running'" in app_js
    assert "status: event.type === 'tool.failed' ? 'failed' : 'completed'" in app_js


def test_agui_web_thinking_indicator_uses_blinking_state_not_ellipsis():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "isThinking: true" in app_js
    assert "thinking-indicator" in app_js
    assert "message.isThinking = false" in app_js
    assert "@keyframes thinkingPulse" in styles


def test_agui_web_mermaid_is_rendered_inline_not_only_file_reference():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "async function renderMermaidInto(" in app_js
    assert "class=\"mermaid-rendered\"" in app_js
    assert "window.mermaid" in app_js
    assert ".mermaid-rendered" in styles


def test_agui_web_inspector_updates_when_artifact_or_status_changes():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "case 'artifact.created':" in app_js
    assert "setRunState(nextState)" in app_js
    assert "renderRightPane();" in app_js


def test_agui_web_filters_tool_role_history_and_ignores_tool_hint_delta():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "if (item.role === 'tool') {" in app_js
    assert "return null;" in app_js
    assert ".filter(Boolean);" in app_js
    assert "if (event.tool_hint || event.payload?.tool_hint) {" in app_js
    assert "break;" in app_js


def test_agui_web_keeps_only_small_tool_flows_after_reply_completion():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "const shouldKeepToolsInline = toolCount > 0;" in app_js
    assert "if (!shouldKeepToolsInline) {" in app_js
    assert "active.toolFlow = [];" in app_js
    assert "active.toolSummaryCount = toolCount;" in app_js


def test_agui_web_dev_only_version_badge_exists_for_cache_debugging():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")
    index_html = (root / "index.html").read_text(encoding="utf-8")

    assert "const FRONTEND_VERSION = '20260309-21'" in app_js
    assert "function shouldShowDevVersionBadge()" in app_js
    assert "dev-version-badge" in app_js
    assert ".dev-version-badge" in styles
    assert "app.js?v=20260309-21" in index_html


def test_agui_web_renders_assistant_markdown_and_compact_tool_summary():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function renderMarkdown(input)" in app_js
    assert "window.marked" in app_js
    assert "window.DOMPurify" in app_js
    assert "body.innerHTML = renderMarkdown(cleanedContent);" in app_js
    assert "appendToolHint(" in app_js
    assert "isRedundantToolSignatureHint(" in app_js
    assert "formatToolHintTone(" in app_js
    assert "formatToolSummaryTone(" in app_js
    assert "已运行 $1" in app_js
    assert "正在扫描 $1" in app_js
    assert "tool-hint-item" in app_js
    assert "tool-hint-open" in app_js
    assert "codex-style-tools" in app_js
    assert "tool-compact-summary" in app_js
    assert ".tool-compact-summary" in styles
    assert ".tool-hint-item" in styles
    assert ".tool-hint-open" in styles
    assert ".md-code" in styles
    assert "const transientAssistant = (() => {" in app_js


def test_agui_web_auto_scroll_is_anchored_to_sent_message_then_follows_stream():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "scrollAnchorMessageId" in app_js
    assert "followRunOutput" in app_js
    assert "state.scrollAnchorMessageId = userMessageId;" in app_js
    assert "state.followRunOutput = true;" in app_js
    assert "state.followRunOutput = false;" in app_js
    assert "function adjustTranscriptScroll()" in app_js
    assert "if (!chunk) {" in app_js


def test_agui_web_clickable_path_references_are_inline_and_open_split_preview():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function extractPathReferences(" in app_js
    assert "function enhancePathReferencesInline(" in app_js
    assert "async function canPreviewPathRef(" in app_js
    assert "pathPreviewCache" in app_js
    assert "pathPreviewPending" in app_js
    assert "function openPathPreviewByReference(" in app_js
    assert "/workspace/preview?path=" in app_js
    assert "path-inline-reference" in app_js
    assert ".path-inline-reference" in styles


def test_agui_web_tool_stage_is_rendered_before_assistant_body_and_thinking_tail():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "const toolStage = document.createElement('div');" in app_js
    assert "renderToolFlow(toolStage, message);" in app_js
    assert "function renderThinkingTail(container, message)" in app_js
    assert "state.pendingAssistantId === message.id" in app_js
    assert "if (!String(message.content || '').trim()) {" in app_js
    assert ".thinking-tail" in styles
    assert "if (/^\\/[^./]+$/.test(cleaned)) {" in app_js
    assert "const allowed = new Set([" in app_js
    assert "const basenameAllowed = new Set([" in app_js


def test_agui_web_mermaid_inline_has_no_extra_buttons_and_uses_split_preview():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "function renderMermaidArtifact(" in app_js
    assert "block.addEventListener('click'" in app_js
    assert "copy-mermaid-source" in app_js
    assert "mermaid-open" not in app_js
    assert "mermaid-copy" not in app_js


def test_agui_web_auto_scroll_is_anchored_to_sent_message_then_follows_stream():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")

    assert "scrollAnchorMessageId" in app_js
    assert "followRunOutput" in app_js
    assert "state.scrollAnchorMessageId = userMessageId;" in app_js
    assert "state.followRunOutput = true;" in app_js
    assert "state.followRunOutput = false;" in app_js


def test_agui_web_clickable_path_references_open_split_preview_with_content():
    root = Path(r"D:/workspace/Nano-claw/nanobot/.worktrees/agui-implementation/apps/agui-web")
    app_js = (root / "src" / "app.js").read_text(encoding="utf-8")
    styles = (root / "src" / "styles.css").read_text(encoding="utf-8")

    assert "function extractPathReferences(" in app_js
    assert "function openPathPreviewByReference(" in app_js
    assert "/workspace/preview?path=" in app_js
    assert "artifact.content" in app_js
    assert "path-reference" in app_js
    assert ".path-reference" in styles
