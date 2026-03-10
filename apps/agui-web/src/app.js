const state = {
  apiBase: readStoredApiBase(),
  sessions: [],
  currentSessionId: null,
  messages: [],
  toolEvents: [],
  artifacts: [],
  interrupts: [],
  pendingInterrupt: null,
  eventSource: null,
  pendingAssistantId: null,
  attachments: [],
  rightPaneMode: 'inspector',
  previewArtifactId: null,
  connectionStatus: 'offline',
  runState: 'idle',
  activeTaskCount: 0,
  activeSkills: [],
  lastEventAt: null,
  isSending: false,
  isUploading: false,
  fileStatus: '未选择文件',
  previewDiagramMode: 'rendered',
  scrollAnchorMessageId: null,
  followRunOutput: false,
  pathPreviewCache: {},
  pathPreviewPending: {},
};

const app = document.getElementById('app');
let ui;
const FRONTEND_VERSION = '20260309-21';

function readStoredApiBase() {
  try {
    return localStorage.getItem('nanobot.agui.base') || 'http://127.0.0.1:8000';
  } catch {
    return 'http://127.0.0.1:8000';
  }
}

function persistApiBase(value) {
  try {
    localStorage.setItem('nanobot.agui.base', value);
  } catch {
    // Best-effort only.
  }
}

function renderFatalError(error) {
  if (!app) {
    return;
  }
  app.innerHTML = `
    <div class="app-shell fatal-shell">
      <section class="chat-panel fatal-panel">
        <h1>nanobot webchat</h1>
        <p class="fatal-text">${String(error && error.message ? error.message : error)}</p>
      </section>
    </div>
  `;
}

function renderAppShell() {
  if (!app) {
    throw new Error('Missing #app mount element');
  }

  const devBadge = shouldShowDevVersionBadge()
    ? `<div class="dev-version-badge" title="frontend build">${FRONTEND_VERSION}</div>`
    : '';
  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-kicker">AI应用使能组</div>
          <h1>智能体工作台</h1>
        </div>

        <div class="api-config">
          <label for="api-base">后端地址</label>
          <div class="api-row">
            <input id="api-base" value="${state.apiBase}" />
            <button id="save-base" class="btn ghost">保存</button>
          </div>
        </div>

        <div class="sidebar-actions">
          <button id="new-session" class="btn primary">新建对话</button>
          <button id="delete-current-session" class="btn ghost danger">删除当前</button>
        </div>

        <div class="sessions-head">会话列表</div>
        <div id="session-list" class="session-list"></div>
      </aside>

      <main class="chat-panel">
        <header class="chat-header">
          <div class="chat-title-wrap">
            <div class="chat-kicker">当前会话</div>
            <h2 id="session-title">未选择会话</h2>
          </div>
          <div class="status-bar">
            <span id="connection-chip" class="chip">离线</span>
            <span id="run-chip" class="chip">空闲</span>
            <span id="last-event" class="chip muted">暂无事件</span>
          </div>
        </header>

        <section id="transcript" class="transcript">
          <div class="empty">新建或选择会话开始对话。</div>
        </section>

        <section class="composer-wrap">
          <div id="interrupts" class="interrupts"></div>
          <div id="attachments" class="attachments"></div>
          <textarea id="composer" placeholder="输入消息... Enter发送，Shift+Enter换行"></textarea>
          <div class="composer-actions">
            <input id="file-input" type="file" multiple hidden />
            <label for="file-input" id="file-picker" class="btn ghost file-picker">选择文件</label>
            <span id="file-status" class="file-status">未选择文件</span>
            <button id="send-message" class="btn primary">发送</button>
          </div>
        </section>
      </main>

      <aside id="right-pane" class="right-pane"></aside>

      <div id="image-viewer" class="image-viewer hidden" role="dialog" aria-modal="true">
        <button id="image-viewer-close" class="btn ghost image-viewer-close">关闭</button>
        <img id="image-viewer-img" class="image-viewer-img" alt="preview" />
      </div>
      ${devBadge}
    </div>
  `;
}

function shouldShowDevVersionBadge() {
  const host = String(window.location.hostname || '').toLowerCase();
  return host === 'localhost' || host === '127.0.0.1' || host === '::1';
}

function getUi() {
  return {
    apiBase: document.getElementById('api-base'),
    saveBase: document.getElementById('save-base'),
    newSession: document.getElementById('new-session'),
    deleteCurrentSession: document.getElementById('delete-current-session'),
    sessionList: document.getElementById('session-list'),
    sessionTitle: document.getElementById('session-title'),
    transcript: document.getElementById('transcript'),
    rightPane: document.getElementById('right-pane'),
    imageViewer: document.getElementById('image-viewer'),
    imageViewerImg: document.getElementById('image-viewer-img'),
    imageViewerClose: document.getElementById('image-viewer-close'),
    interrupts: document.getElementById('interrupts'),
    attachments: document.getElementById('attachments'),
    composer: document.getElementById('composer'),
    sendMessage: document.getElementById('send-message'),
    fileInput: document.getElementById('file-input'),
    fileStatus: document.getElementById('file-status'),
    filePicker: document.getElementById('file-picker'),
    connectionChip: document.getElementById('connection-chip'),
    runChip: document.getElementById('run-chip'),
    lastEvent: document.getElementById('last-event'),
  };
}

function normalizeMessageContent(content) {
  if (typeof content === 'string') {
    const trimmed = content.trim();
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      try {
        return normalizeMessageContent(JSON.parse(trimmed));
      } catch {
        // Keep original string when it's not valid JSON content blocks.
      }
    }
    return content;
  }
  if (Array.isArray(content)) {
    const chunks = [];
    for (const item of content) {
      if (!item || typeof item !== 'object') {
        continue;
      }
      if (item.type === 'text' && typeof item.text === 'string') {
        chunks.push(item.text);
      } else if (item.type === 'image_url') {
        chunks.push('[image]');
      }
    }
    return chunks.join('\n').trim() || '[attachment]';
  }
  if (content == null) {
    return '';
  }
  return String(content);
}

function normalizeMessageAttachments(attachments) {
  if (!Array.isArray(attachments)) {
    return [];
  }
  return attachments.filter(item => item && typeof item === 'object');
}

function cleanImagePlaceholder(content, attachments) {
  if (!content) {
    return '';
  }
  const hasImage = normalizeMessageAttachments(attachments).some(isImageAttachment);
  if (!hasImage) {
    return content;
  }
  return String(content)
    .split('\n')
    .filter(line => line.trim() !== '[image]')
    .join('\n')
    .trim();
}

function extractMermaidBlocks(content) {
  const text = String(content || '');
  const regex = /```mermaid\s*([\s\S]*?)```/g;
  const blocks = [];
  let match;
  while ((match = regex.exec(text)) !== null) {
    blocks.push(match[1].trim());
  }
  return blocks;
}

function stripMermaidBlocks(content) {
  return String(content || '').replace(/```mermaid\s*[\s\S]*?```/g, '').trim();
}

function filePreviewUrl(attachment) {
  if (!attachment || !attachment.file_id) {
    return null;
  }
  return `${state.apiBase}/files/${attachment.file_id}`;
}

function isImageAttachment(attachment) {
  const mime = String(attachment?.mime_type || '').toLowerCase();
  if (mime.startsWith('image/')) {
    return true;
  }
  const name = String(attachment?.filename || '').toLowerCase();
  return name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.jpeg') || name.endsWith('.webp');
}

function isMermaidAttachment(attachment) {
  const type = String(attachment?.type || '').toLowerCase();
  if (type === 'diagram') {
    return true;
  }
  const format = String(attachment?.metadata?.diagram_format || '').toLowerCase();
  if (format === 'mermaid') {
    return true;
  }
  const name = String(attachment?.filename || attachment?.title || '').toLowerCase();
  return name.endsWith('.mmd') || name.endsWith('.mermaid');
}

function updateStatusBar() {
  if (!ui) {
    return;
  }

  ui.connectionChip.textContent = state.connectionStatus === 'online' ? '在线' : '离线';
  ui.connectionChip.className = `chip ${state.connectionStatus === 'online' ? 'ok' : 'warn'}`;

  const runLabel = state.runState === 'running'
    ? '正在思考'
    : state.isUploading
      ? '上传文件中...'
      : state.isSending
        ? '发送中...'
        : '空闲';

  ui.runChip.textContent = runLabel;
  ui.runChip.className = `chip ${state.runState === 'running' || state.isSending || state.isUploading ? 'busy' : ''}`;
  ui.lastEvent.textContent = state.lastEventAt
    ? `最近事件 ${new Date(state.lastEventAt).toLocaleTimeString()}`
    : '暂无事件';

  ui.sendMessage.disabled = state.isSending || state.isUploading;
  ui.sendMessage.textContent = state.isUploading ? '上传中...' : state.isSending ? '发送中...' : '发送';
  ui.fileStatus.textContent = state.fileStatus;
  ui.filePicker.classList.toggle('disabled', state.isUploading || state.isSending);
}

function setConnectionStatus(status) {
  state.connectionStatus = status;
  updateStatusBar();
  renderRightPane();
}

function setRunState(nextState) {
  state.runState = nextState;
  state.lastEventAt = Date.now();
  updateStatusBar();
  renderRightPane();
}

function setSending(sending) {
  state.isSending = sending;
  updateStatusBar();
}

function setUploading(uploading) {
  state.isUploading = uploading;
  updateStatusBar();
}

async function request(path, options = {}) {
  const response = await fetch(`${state.apiBase}${path}`, options);
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `${response.status} ${response.statusText}`);
  }
  return response.json();
}

function toUiMessages(items) {
  return (items || [])
    .map((item, index) => {
      if (item.role === 'tool') {
        return null;
      }
      return {
        id: `history-${index}`,
        role: item.role === 'assistant' ? 'assistant' : item.role === 'system' ? 'system' : 'user',
        content: normalizeMessageContent(item.content),
        attachments: normalizeMessageAttachments(item.attachments),
      };
    })
    .filter(Boolean);
}

export async function createSession() {
  return request('/sessions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
}

async function refreshSessions(selectId = state.currentSessionId) {
  try {
    const data = await request('/sessions');
    state.sessions = data.items || [];

    if (selectId) {
      state.currentSessionId = selectId;
    } else if (!state.currentSessionId && state.sessions.length > 0) {
      state.currentSessionId = state.sessions[0].session_id;
    }

    renderSessions();

    if (state.currentSessionId) {
      await selectSession(state.currentSessionId);
    }
  } catch (error) {
    renderSystemMessage(`加载会话失败：${error.message}`);
    setConnectionStatus('offline');
  }
}

function renderSessions() {
  ui.sessionList.innerHTML = '';

  if (state.sessions.length === 0) {
    ui.sessionList.innerHTML = '<div class="empty">暂无会话。</div>';
    return;
  }

  for (const session of state.sessions) {
    const button = document.createElement('button');
    button.className = `session-item${session.session_id === state.currentSessionId ? ' active' : ''}`;
    button.innerHTML = `<strong>${session.session_id}</strong><span>${session.updated_at || ''}</span>`;
    button.addEventListener('click', () => {
      void selectSession(session.session_id);
    });
    ui.sessionList.appendChild(button);
  }
}

async function deleteSession(sessionId = state.currentSessionId) {
  if (!sessionId) {
    return;
  }

  try {
    await request(`/sessions/${sessionId}`, { method: 'DELETE' });
    if (state.currentSessionId === sessionId) {
      state.currentSessionId = null;
      state.messages = [];
      renderTranscript();
      if (state.eventSource) {
        state.eventSource.close();
      }
    }
    await refreshSessions();
  } catch (error) {
    renderSystemMessage(`删除会话失败：${error.message}`);
  }
}

async function fetchAndRenderHistory(sessionId) {
  const history = await request(`/sessions/${sessionId}/messages`);
  state.messages = toUiMessages(history.items);
  renderTranscript();
}

async function syncHistoryAfterCompletion(sessionId) {
  const attempts = 10;
  const delayMs = 350;
  const transientAssistant = (() => {
    for (let i = state.messages.length - 1; i >= 0; i -= 1) {
      const msg = state.messages[i];
      if (msg.role === 'assistant') {
        return {
          toolFlow: Array.isArray(msg.toolFlow) ? msg.toolFlow : [],
          toolSummaryCount: msg.toolSummaryCount || 0,
          progressHints: Array.isArray(msg.progressHints) ? msg.progressHints : [],
        };
      }
    }
    return null;
  })();

  for (let i = 0; i < attempts; i += 1) {
    try {
      const history = await request(`/sessions/${sessionId}/messages`);
      const mapped = toUiMessages(history.items);
      if (mapped.length > 0) {
        state.messages = mapped;
        if (transientAssistant) {
          const last = state.messages[state.messages.length - 1];
          if (last && last.role === 'assistant') {
            last.toolFlow = transientAssistant.toolFlow;
            last.toolSummaryCount = transientAssistant.toolSummaryCount;
            last.progressHints = transientAssistant.progressHints;
          }
        }
        renderTranscript();
      }

      const last = mapped[mapped.length - 1];
      const done = !!last && last.role === 'assistant' && String(last.content || '').trim().length > 0;
      if (done) {
        return;
      }
    } catch {
      // retry
    }

    await new Promise(resolve => setTimeout(resolve, delayMs));
  }
}

async function selectSession(sessionId) {
  state.currentSessionId = sessionId;
  state.pendingAssistantId = null;
  state.interrupts = [];
  renderSessions();
  ui.sessionTitle.textContent = sessionId;

  try {
    await fetchAndRenderHistory(sessionId);
    connectEventStream(sessionId);
  } catch (error) {
    renderSystemMessage(`加载历史消息失败：${error.message}`);
    setConnectionStatus('offline');
  }
}

function connectEventStream(sessionId) {
  if (state.eventSource) {
    state.eventSource.close();
  }

  const source = new EventSource(`${state.apiBase}/sessions/${sessionId}/events`);
  state.eventSource = source;
  setConnectionStatus('online');

  ['run.started', 'message.started', 'message.delta', 'message.completed', 'tool.started', 'tool.completed', 'tool.failed', 'task.started', 'task.updated', 'task.completed', 'task.failed', 'artifact.created', 'artifact.updated', 'artifact.referenced', 'interrupt.requested', 'interrupt.resolved', 'error'].forEach(name => {
    source.addEventListener(name, event => {
      setConnectionStatus('online');
      state.lastEventAt = Date.now();
      updateStatusBar();
      handleEvent(JSON.parse(event.data));
    });
  });

  source.onerror = () => {
    setConnectionStatus('offline');
    renderSystemMessage('事件流连接已断开。');
  };
}

function handleEvent(event) {
  switch (event.type) {
    case 'run.started':
      setRunState('running');
      ensurePendingAssistantMessage();
      renderTranscript();
      break;

    case 'message.started':
      setRunState('running');
      ensurePendingAssistantMessage();
      renderTranscript();
      break;

    case 'message.delta':
      if (event.tool_hint || event.payload?.tool_hint) {
        appendToolHint(event.content || event.payload?.content || '');
        break;
      }
      {
        const chunk = event.content || event.payload?.content || '';
        if (!chunk) {
          break;
        }
        appendAssistantChunk(chunk, false);
      }
      break;

    case 'message.completed':
      if (typeof event.content === 'string' && event.content.length > 0) {
        appendAssistantChunk(event.content, true);
      }
      {
        const active = getActiveAssistantMessage();
        if (active) {
          active.isThinking = false;
          const toolCount = Array.isArray(active.toolFlow) ? active.toolFlow.length : 0;
          const shouldKeepToolsInline = toolCount > 0;
          active.toolSummaryCount = toolCount;
          if (!shouldKeepToolsInline) {
            active.toolFlow = [];
          } else {
            active.toolFlow = active.toolFlow.map(item => ({
              ...item,
              status: item.status === 'running' ? 'completed' : item.status,
            }));
          }
        }
      }
      state.pendingAssistantId = null;
      state.followRunOutput = false;
      setRunState('idle');
      if (state.currentSessionId) {
        void syncHistoryAfterCompletion(state.currentSessionId);
      }
      break;

    case 'interrupt.requested':
      upsertInterrupt(event);
      renderRightPane();
      break;

    case 'tool.started':
    case 'tool.completed':
    case 'tool.failed':
      upsertToolEventForActiveMessage(event);
      renderTranscript();
      renderRightPane();
      break;

    case 'artifact.created':
    case 'artifact.updated':
    case 'artifact.referenced':
      upsertArtifactFromEvent(event);
      renderRightPane();
      break;

    case 'task.started':
    case 'task.updated':
      state.activeTaskCount += 1;
      renderRightPane();
      break;

    case 'task.completed':
    case 'task.failed':
      state.activeTaskCount = Math.max(0, state.activeTaskCount - 1);
      renderRightPane();
      break;

    case 'interrupt.resolved':
      state.interrupts = state.interrupts.map(item => (
        item.interrupt_id === event.interrupt_id
          ? {
              ...item,
              status: 'resolved',
              resultSummary: `Resolved: ${String(event.value ?? 'submitted')}`,
            }
          : item
      ));
      state.pendingInterrupt = state.interrupts.find(item => item.status !== 'resolved') || null;
      renderInterrupts();
      renderRightPane();
      break;

    case 'error':
      state.followRunOutput = false;
      setRunState('idle');
      renderSystemMessage(`Error: ${event.message || 'unknown error'}`);
      break;

    default:
      break;
  }
}

function appendAssistantChunk(chunk, replace = false) {
  const target = ensurePendingAssistantMessage();

  const message = target;
  message.isThinking = false;
  target.content = replace ? chunk : `${target.content}${chunk}`;
  renderTranscript();
}

function ensurePendingAssistantMessage() {
  const existing = state.pendingAssistantId
    ? state.messages.find(message => message.id === state.pendingAssistantId)
    : null;
  if (existing) {
    return existing;
  }
  const pendingId = `assistant-${Date.now()}`;
  const pendingMessage = {
    id: pendingId,
    role: 'assistant',
    content: '',
    attachments: [],
    toolFlow: [],
    completedToolCount: 0,
    toolSummaryCount: 0,
    progressHints: [],
    isThinking: true,
  };
  state.pendingAssistantId = pendingId;
  state.messages.push(pendingMessage);
  return pendingMessage;
}

function getActiveAssistantMessage() {
  if (state.pendingAssistantId) {
    const pending = state.messages.find(message => message.id === state.pendingAssistantId);
    if (pending) {
      return pending;
    }
  }
  for (let i = state.messages.length - 1; i >= 0; i -= 1) {
    if (state.messages[i].role === 'assistant') {
      return state.messages[i];
    }
  }
  return null;
}

function upsertToolEventForActiveMessage(event) {
  const active = event.type === 'tool.started'
    ? ensurePendingAssistantMessage()
    : getActiveAssistantMessage();
  if (!active) return;
  active.toolFlow = active.toolFlow || [];
  const payload = event.payload || {};
  const toolCallId = payload.tool_call_id || `${event.type}-${Date.now()}`;
  if (event.type === 'tool.started') {
    active.toolFlow.push({
      toolCallId,
      summary: payload.summary || payload.tool_name || 'Running tool',
      toolName: payload.tool_name || '',
      argumentsPreview: payload.arguments_preview || '',
      resultPreview: '',
      status: 'running',
    });
    return;
  }
  const idx = active.toolFlow.findIndex(item => item.toolCallId === toolCallId);
  if (idx >= 0) {
    active.toolFlow[idx] = {
      ...active.toolFlow[idx],
      resultPreview: payload.result_preview || '',
      durationMs: payload.duration_ms,
      status: event.type === 'tool.failed' ? 'failed' : 'completed',
    };
  } else {
    active.toolFlow.push({
      toolCallId,
      summary: payload.summary || payload.tool_name || 'Tool',
      toolName: payload.tool_name || '',
      argumentsPreview: payload.arguments_preview || '',
      resultPreview: payload.result_preview || '',
      durationMs: payload.duration_ms,
      status: event.type === 'tool.failed' ? 'failed' : 'completed',
    });
  }
}

function upsertArtifactFromEvent(event) {
  const artifact = event.artifact || event.payload?.artifact;
  if (!artifact) {
    return;
  }
  const artifactId = artifact.artifact_id || artifact.file_id || artifact.path;
  if (!artifactId) {
    return;
  }
  const idx = state.artifacts.findIndex(item => item.artifact_id === artifactId);
  if (idx >= 0) {
    state.artifacts[idx] = { ...state.artifacts[idx], ...artifact, artifact_id: artifactId };
  } else {
    state.artifacts.unshift({ ...artifact, artifact_id: artifactId });
  }
}

function openImageViewer(src, alt) {
  if (!ui?.imageViewer || !ui?.imageViewerImg) {
    return;
  }
  ui.imageViewerImg.src = src;
  ui.imageViewerImg.alt = alt || 'preview';
  ui.imageViewer.classList.remove('hidden');
}

function closeImageViewer() {
  if (!ui?.imageViewer || !ui?.imageViewerImg) {
    return;
  }
  ui.imageViewer.classList.add('hidden');
  ui.imageViewerImg.removeAttribute('src');
}

function renderMessageAttachments(container, attachments) {
  if (!attachments || attachments.length === 0) {
    return;
  }

  const wrap = document.createElement('div');
  wrap.className = 'message-attachments';

  for (const attachment of attachments) {
    if (isMermaidAttachment(attachment)) {
      wrap.appendChild(renderMermaidArtifact(attachment));
      continue;
    }

    if (isImageAttachment(attachment) && attachment.file_id) {
      const src = filePreviewUrl(attachment);
      if (src) {
        const img = document.createElement('img');
        img.className = 'message-image';
        img.style.width = '72px';
        img.style.height = '72px';
        img.style.cursor = 'zoom-in';
        img.title = 'Click to enlarge';
        img.loading = 'lazy';
        img.alt = attachment.filename || 'image';
        img.src = src;
        img.addEventListener('click', () => {
          openImageViewer(src, img.alt);
          openArtifactPreview({
            artifact_id: attachment.artifact_id || attachment.file_id,
            type: 'image',
            title: attachment.filename || 'image',
            path: attachment.path,
            mime_type: attachment.mime_type,
          });
        });
        wrap.appendChild(img);
        continue;
      }
    }

    const name = attachment.filename || attachment.file_id || 'file';
    wrap.appendChild(renderArtifactReference(attachment, name));
  }

  container.appendChild(wrap);
}

function renderMermaidArtifact(attachment) {
  const block = document.createElement('div');
  block.className = 'mermaid-artifact';
  const source = String(attachment.preview_text || attachment.source_text || 'graph TD;A-->B');
  const title = attachment.title || attachment.filename || attachment.artifact_id || 'Mermaid 图';
  const renderId = `mermaid-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  block.innerHTML = `
    <div class="mermaid-head">
      <strong>${title}</strong>
    </div>
    <div id="${renderId}" class="mermaid-rendered"></div>
  `;
  void renderMermaidInto(block.querySelector(`#${renderId}`), source);
  block.addEventListener('click', () => {
    openArtifactPreview({
      artifact_id: attachment.artifact_id || attachment.file_id || title,
      type: 'diagram',
      title,
      path: attachment.path,
      mime_type: attachment.mime_type || 'text/plain',
      preview_text: source,
    });
  });
  return block;
}

let mermaidModulePromise = null;

function getMermaid() {
  if (window.mermaid) {
    return Promise.resolve(window.mermaid);
  }
  if (!mermaidModulePromise) {
    mermaidModulePromise = import('https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs')
      .then(mod => mod.default || mod);
  }
  return mermaidModulePromise;
}

async function renderMermaidInto(targetEl, source) {
  if (!targetEl) {
    return;
  }
  try {
    const mermaid = await getMermaid();
    if (mermaid && typeof mermaid.initialize === 'function') {
      mermaid.initialize({ startOnLoad: false, securityLevel: 'loose' });
    }
    if (window.mermaid && typeof window.mermaid.render === 'function') {
      const id = `mmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const rendered = await window.mermaid.render(id, source);
      targetEl.innerHTML = rendered.svg || '';
      return;
    }
    if (mermaid && typeof mermaid.render === 'function') {
      const id = `mmd-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      const rendered = await mermaid.render(id, source);
      targetEl.innerHTML = rendered.svg || '';
      return;
    }
    targetEl.textContent = source;
  } catch {
    targetEl.textContent = source;
  }
}

function renderArtifactReference(attachment, fallbackTitle) {
  const name = fallbackTitle || attachment.filename || attachment.file_id || 'file';
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'artifact-reference';
  btn.textContent = name;
  btn.addEventListener('click', () => {
    openArtifactPreview({
      artifact_id: attachment.artifact_id || attachment.file_id || name,
      type: attachment.mime_type && attachment.mime_type.startsWith('image/') ? 'image' : 'file',
      title: name,
      path: attachment.path,
      mime_type: attachment.mime_type,
    });
  });
  return btn;
}

function renderTranscript() {
  ui.transcript.innerHTML = '';

  if (state.messages.length === 0) {
    ui.transcript.innerHTML = '<div class="empty">暂无消息。</div>';
    return;
  }

  for (const message of state.messages) {
    const div = document.createElement('div');
    div.className = `message ${message.role}`;
    div.dataset.messageId = message.id;
    if (message.role === 'assistant') {
      const toolStage = document.createElement('div');
      renderToolFlow(toolStage, message);
      if (toolStage.childElementCount > 0) {
        div.appendChild(toolStage);
      }
    }

    const body = document.createElement('div');
    body.className = 'message-body';
    const inlineMermaidBlocks = message.role === 'assistant' ? extractMermaidBlocks(message.content) : [];
    if (message.role === 'assistant' && message.isThinking && !String(message.content || '').trim()) {
      body.innerHTML = '<span class="thinking-indicator">正在思考</span>';
    } else {
      const contentWithoutMermaid = inlineMermaidBlocks.length > 0
        ? stripMermaidBlocks(message.content)
        : message.content;
      const cleanedContent = cleanImagePlaceholder(contentWithoutMermaid, message.attachments);
      if (message.role === 'assistant') {
        body.innerHTML = renderMarkdown(cleanedContent);
        void enhancePathReferencesInline(body, cleanedContent);
      } else {
        body.textContent = cleanedContent;
      }
    }
    div.appendChild(body);

    renderMessageAttachments(div, normalizeMessageAttachments(message.attachments));
    for (const source of inlineMermaidBlocks) {
      div.appendChild(renderMermaidArtifact({ type: 'diagram', title: 'Mermaid', preview_text: source }));
    }
    renderThinkingTail(div, message);
    ui.transcript.appendChild(div);
  }
  adjustTranscriptScroll();
}

function renderToolFlow(container) {
  const message = arguments[1];
  if (!message) {
    return;
  }
  if (Array.isArray(message.progressHints) && message.progressHints.length > 0) {
    const hints = document.createElement('div');
    hints.className = 'tool-hints';
    for (const text of message.progressHints) {
      const item = document.createElement('div');
      item.className = 'tool-hint-item';
      item.textContent = text;
      const refs = extractPathReferences(text).map(normalizePathReference).filter(Boolean);
      if (refs.length > 0) {
        const ref = refs[0];
        const action = document.createElement('button');
        action.type = 'button';
        action.className = 'tool-hint-open';
        action.textContent = '打开';
        action.addEventListener('click', () => {
          void openPathPreviewByReference(ref);
        });
        item.appendChild(action);
      }
      hints.appendChild(item);
    }
    container.appendChild(hints);
  }
  const toolFlow = Array.isArray(message.toolFlow) ? message.toolFlow : [];
  if (toolFlow.length === 0 && !(message.toolSummaryCount > 0)) {
    return;
  }
  if (toolFlow.length === 0 && message.toolSummaryCount > 0) {
    const compact = document.createElement('div');
    compact.className = 'tool-compact-summary';
    compact.textContent = `本轮调用了 ${message.toolSummaryCount} 个工具`;
    container.appendChild(compact);
    return;
  }
  const wrap = document.createElement('div');
  wrap.className = 'tool-flow codex-style-tools';
  for (const item of toolFlow) {
    const details = document.createElement('details');
    details.className = 'tool-flow-item';
    details.open = false;
    const summary = document.createElement('summary');
    const statusLabel = item.status === 'running' ? '进行中' : item.status === 'failed' ? '失败' : '完成';
    summary.textContent = formatToolSummaryTone(item.summary || item.toolName || 'Tool', item.status, statusLabel);
    details.appendChild(summary);
    details.classList.add(`tool-${item.status || 'running'}`);

    const detail = document.createElement('div');
    detail.className = 'tool-flow-detail';
    detail.innerHTML = `
      <div><strong>工具：</strong>${item.toolName || '-'}</div>
      <div><strong>参数：</strong>${item.argumentsPreview || '-'}</div>
      <div><strong>结果：</strong>${item.resultPreview || (item.status === 'running' ? '执行中...' : '-')}</div>
      <div><strong>耗时：</strong>${item.durationMs != null ? `${item.durationMs} ms` : '-'}</div>
    `;
    details.appendChild(detail);
    wrap.appendChild(details);
  }
  container.appendChild(wrap);
}

function renderThinkingTail(container, message) {
  if (!message || message.role !== 'assistant') {
    return;
  }
  if (!(state.runState === 'running' && state.pendingAssistantId === message.id)) {
    return;
  }
  // Avoid duplicate thinking indicators when message body is still empty.
  if (!String(message.content || '').trim()) {
    return;
  }
  const tail = document.createElement('div');
  tail.className = 'thinking-tail';
  tail.innerHTML = '<span class="thinking-indicator">正在思考</span>';
  container.appendChild(tail);
}

function adjustTranscriptScroll() {
  if (!ui?.transcript) {
    return;
  }
  if (state.scrollAnchorMessageId) {
    const el = ui.transcript.querySelector(`[data-message-id="${state.scrollAnchorMessageId}"]`);
    if (el && typeof el.scrollIntoView === 'function') {
      el.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }
    state.scrollAnchorMessageId = null;
  }
  if (state.followRunOutput) {
    ui.transcript.scrollTop = ui.transcript.scrollHeight;
  }
}

function appendToolHint(text) {
  const active = ensurePendingAssistantMessage();
  const hint = String(text || '').trim();
  if (!hint) {
    return;
  }
  if (isRedundantToolSignatureHint(hint)) {
    return;
  }
  active.progressHints = Array.isArray(active.progressHints) ? active.progressHints : [];
  const normalized = formatToolHintTone(hint.replace(/\s+/g, ' '));
  if (!active.progressHints.includes(normalized)) {
    active.progressHints.push(normalized);
  }
  if (active.progressHints.length > 6) {
    active.progressHints = active.progressHints.slice(-6);
  }
  renderTranscript();
}

function isRedundantToolSignatureHint(hint) {
  const compact = String(hint || '').trim();
  if (!compact) {
    return true;
  }
  // e.g. list_dir("C:\\path") / shell("pwd")
  return /^[a-zA-Z_]\w*\(.+\)$/.test(compact);
}

function formatToolSummaryTone(text, status, statusLabel) {
  const raw = String(text || '').trim();
  const runningMatch = raw.match(/^Running\s+(.+)$/i);
  if (runningMatch) {
    const target = runningMatch[1];
    if (status === 'running') {
      return `正在运行 ${target} · ${statusLabel}`;
    }
    if (status === 'failed') {
      return `运行失败 ${target} · ${statusLabel}`;
    }
    return `已运行 ${target} · ${statusLabel}`;
  }
  return `${raw} · ${statusLabel}`;
}

function formatToolHintTone(text) {
  const raw = String(text || '').trim();
  if (!raw) {
    return raw;
  }
  const patterns = [
    [/^running\s+(.+)$/i, '已运行 $1'],
    [/^scanning\s+(.+)$/i, '正在扫描 $1'],
    [/^listing\s+(.+)$/i, '正在列出 $1'],
    [/^reading\s+(.+)$/i, '正在读取 $1'],
    [/^checking\s+(.+)$/i, '正在检查 $1'],
    [/^searching\s+(.+)$/i, '正在搜索 $1'],
    [/^loaded\s+(.+)$/i, '已加载 $1'],
  ];
  for (const [regex, replacement] of patterns) {
    if (regex.test(raw)) {
      return raw.replace(regex, replacement);
    }
  }
  return raw;
}

function extractPathReferences(content) {
  const text = String(content || '');
  const refs = new Set();
  const inlineCodeMatches = text.match(/`([^`]+)`/g) || [];
  for (const token of inlineCodeMatches) {
    const value = token.slice(1, -1).trim();
    if (looksLikePath(value)) {
      refs.add(value);
    }
  }
  const rawPathMatches = text.match(/([A-Za-z]:\\[^\s"'`]*\.[A-Za-z0-9]{1,8}|\.{0,2}\/[^\s"'`]*\.[A-Za-z0-9]{1,8}|[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)+\.[A-Za-z0-9]{1,8}|[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,8})/g) || [];
  for (const value of rawPathMatches) {
    if (looksLikePath(value)) {
      refs.add(value);
    }
  }
  return Array.from(refs).slice(0, 8);
}

function looksLikePath(value) {
  const v = String(value || '').trim();
  if (!v) return false;
  if (v.includes('://')) return false;
  const cleaned = v
    .replace(/#L\d+$/i, '')
    .replace(/:L\d+$/i, '')
    .replace(/#.*$/, '')
    .trim();
  // Reject slash-like plain words such as "/铜色系".
  if (/^\/[^./]+$/.test(cleaned)) {
    return false;
  }
  const extMatch = cleaned.match(/\.([A-Za-z0-9]{1,8})$/);
  if (!extMatch) {
    return false;
  }
  const ext = extMatch[1].toLowerCase();
  const allowed = new Set([
    'py', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'scss', 'json', 'yaml', 'yml',
    'md', 'txt', 'sh', 'bat', 'ps1', 'toml', 'ini', 'csv', 'sql', 'xml',
    'png', 'jpg', 'jpeg', 'webp', 'gif', 'svg', 'pdf',
  ]);
  if (!allowed.has(ext)) {
    return false;
  }
  const hasSeparator = /[\\/]/.test(cleaned) || /^[A-Za-z]:/.test(cleaned);
  if (hasSeparator) {
    return true;
  }
  const basenameAllowed = new Set([
    'py', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'scss', 'json', 'yaml', 'yml',
    'md', 'txt', 'sh', 'bat', 'ps1', 'toml', 'ini', 'csv', 'sql', 'xml',
  ]);
  return basenameAllowed.has(ext);
}

function renderPathReferences(container, content) {
  const refs = extractPathReferences(content);
  if (!refs.length) {
    return;
  }
  const wrap = document.createElement('div');
  wrap.className = 'path-references';
  for (const ref of refs) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'path-reference';
    btn.textContent = ref;
    btn.addEventListener('click', () => {
      void openPathPreviewByReference(ref);
    });
    wrap.appendChild(btn);
  }
  container.appendChild(wrap);
}

async function openPathPreviewByReference(pathRef) {
  try {
    const normalizedPath = normalizePathReference(pathRef);
    let cached = state.pathPreviewCache[normalizedPath];
    if (!cached || !cached.ok || !cached.preview) {
      const preview = await request(`/workspace/preview?path=${encodeURIComponent(normalizedPath)}`);
      cached = { ok: true, preview };
      state.pathPreviewCache[normalizedPath] = cached;
    }
    const preview = cached.preview;
    openArtifactPreview({
      artifact_id: `path:${preview.path}`,
      type: preview.viewer_type === 'code' ? 'code' : 'file',
      title: preview.title || preview.path,
      path: preview.path,
      mime_type: preview.mime_type,
      content: preview.content,
    });
  } catch (error) {
    renderSystemMessage(`Path preview failed: ${error.message}`);
  }
}

function normalizePathReference(pathRef) {
  return String(pathRef || '')
    .trim()
    .replace(/^`|`$/g, '')
    .replace(/#L\d+$/i, '')
    .replace(/:L\d+$/i, '')
    .replace(/\\/g, '/');
}

async function enhancePathReferencesInline(container, content) {
  const refs = extractPathReferences(content).map(normalizePathReference).filter(Boolean);
  if (!refs.length) {
    return;
  }
  const uniqRefs = [...new Set(refs)];
  const checks = await Promise.all(uniqRefs.map(ref => canPreviewPathRef(ref)));
  const validRefs = uniqRefs.filter((_ref, idx) => checks[idx]);
  if (!validRefs.length) {
    return;
  }
  const sorted = validRefs.sort((a, b) => b.length - a.length);
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  let node;
  while ((node = walker.nextNode())) {
    const parentTag = node.parentElement?.tagName;
    if (!parentTag || ['A', 'CODE', 'PRE', 'BUTTON'].includes(parentTag)) {
      continue;
    }
    textNodes.push(node);
  }
  for (const textNode of textNodes) {
    const original = textNode.textContent || '';
    let foundRef = null;
    for (const ref of sorted) {
      if (original.includes(ref)) {
        foundRef = ref;
        break;
      }
    }
    if (!foundRef) {
      continue;
    }
    const frag = document.createDocumentFragment();
    let rest = original;
    while (rest.includes(foundRef)) {
      const idx = rest.indexOf(foundRef);
      const head = rest.slice(0, idx);
      if (head) {
        frag.appendChild(document.createTextNode(head));
      }
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'path-inline-reference';
      btn.textContent = foundRef;
      btn.addEventListener('click', () => {
        void openPathPreviewByReference(foundRef);
      });
      frag.appendChild(btn);
      rest = rest.slice(idx + foundRef.length);
    }
    if (rest) {
      frag.appendChild(document.createTextNode(rest));
    }
    textNode.parentNode.replaceChild(frag, textNode);
  }
}

async function canPreviewPathRef(ref) {
  const normalized = normalizePathReference(ref);
  if (!normalized) {
    return false;
  }
  const cached = state.pathPreviewCache[normalized];
  if (cached) {
    return !!cached.ok;
  }
  if (state.pathPreviewPending[normalized]) {
    return state.pathPreviewPending[normalized];
  }
  const pending = (async () => {
    try {
      const preview = await request(`/workspace/preview?path=${encodeURIComponent(normalized)}`);
      state.pathPreviewCache[normalized] = { ok: true, preview };
      return true;
    } catch {
      state.pathPreviewCache[normalized] = { ok: false };
      return false;
    } finally {
      delete state.pathPreviewPending[normalized];
    }
  })();
  state.pathPreviewPending[normalized] = pending;
  return pending;
}

function escapeHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function renderMarkdown(input) {
  const source = String(input || '');
  if (!source.trim()) {
    return '';
  }
  if (window.marked && typeof window.marked.parse === 'function') {
    try {
      const raw = window.marked.parse(source, { gfm: true, breaks: true });
      if (window.DOMPurify && typeof window.DOMPurify.sanitize === 'function') {
        return window.DOMPurify.sanitize(raw);
      }
      return raw;
    } catch {
      // fallback to local parser
    }
  }
  const codeBlocks = [];
  let text = source.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_m, lang, code) => {
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre class="md-code"><code class="lang-${escapeHtml(lang || 'text')}">${escapeHtml(code)}</code></pre>`);
    return `@@CODE_BLOCK_${idx}@@`;
  });
  text = escapeHtml(text);
  text = text
    .replace(/^###\s+(.+)$/gm, '<h4>$1</h4>')
    .replace(/^##\s+(.+)$/gm, '<h3>$1</h3>')
    .replace(/^#\s+(.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  let inList = false;
  const out = [];
  for (const raw of lines) {
    const line = raw.trimEnd();
    const listMatch = line.match(/^\s*-\s+(.+)$/);
    if (listMatch) {
      if (!inList) {
        out.push('<ul>');
        inList = true;
      }
      out.push(`<li>${listMatch[1]}</li>`);
      continue;
    }
    if (inList) {
      out.push('</ul>');
      inList = false;
    }
    if (!line.trim()) {
      out.push('<br />');
    } else if (/^<h[2-4]>/.test(line)) {
      out.push(line);
    } else {
      out.push(`<p>${line}</p>`);
    }
  }
  if (inList) {
    out.push('</ul>');
  }
  let html = out.join('\n');
  html = html.replace(/@@CODE_BLOCK_(\d+)@@/g, (_m, idx) => codeBlocks[Number(idx)] || '');
  return html;
}

function renderSystemMessage(text) {
  state.messages.push({ id: `system-${Date.now()}`, role: 'system', content: text, attachments: [] });
  renderTranscript();
}

async function sendCurrentMessage() {
  if (state.isSending || state.isUploading) {
    return;
  }

  if (!state.currentSessionId) {
    const session = await createSession();
    await refreshSessions(session.session_id);
  }

  const content = ui.composer.value.trim();
  if (!content) {
    return;
  }

  const sentAttachments = [...state.attachments];
  const userMessageId = `user-${Date.now()}`;
  state.messages.push({ id: userMessageId, role: 'user', content, attachments: sentAttachments });
  state.scrollAnchorMessageId = userMessageId;
  state.followRunOutput = true;
  renderTranscript();
  ui.composer.value = '';
  setSending(true);

  try {
    await request(`/sessions/${state.currentSessionId}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content,
        attachments: sentAttachments,
      }),
    });
    state.attachments = [];
    state.fileStatus = '未选择文件';
    renderAttachments();
    updateStatusBar();
  } catch (error) {
    renderSystemMessage(`发送失败：${error.message}`);
    setRunState('idle');
  } finally {
    setSending(false);
  }
}

async function uploadSelectedFiles() {
  const files = Array.from(ui.fileInput.files || []);
  if (files.length === 0) {
    return;
  }

  setUploading(true);
  state.fileStatus = `正在上传 ${files.length} 个文件...`;
  updateStatusBar();

  for (const file of files) {
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${state.apiBase}/files`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `${response.status}`);
      }

      const metadata = await response.json();
      state.attachments.push(metadata);
      if (metadata.artifact) {
        openArtifactPreview(metadata.artifact);
      }
    } catch (error) {
      renderSystemMessage(`Upload failed for ${file.name}: ${error.message}`);
    }
  }

  ui.fileInput.value = '';
  setUploading(false);
  state.fileStatus = state.attachments.length > 0 ? `${state.attachments.length} 个文件待发送` : '未选择文件';
  updateStatusBar();
  renderAttachments();
}

function renderAttachments() {
  ui.attachments.innerHTML = '';

  for (const attachment of state.attachments) {
    const badge = document.createElement('div');
    badge.className = 'badge';
    badge.textContent = `${attachment.filename} - ${attachment.mime_type}`;
    ui.attachments.appendChild(badge);
  }
}

function upsertInterrupt(interrupt) {
  state.pendingInterrupt = interrupt;
  const existing = state.interrupts.findIndex(item => item.interrupt_id === interrupt.interrupt_id);
  if (existing >= 0) {
    state.interrupts[existing] = interrupt;
  } else {
    state.interrupts.push(interrupt);
  }
  renderInterrupts();
}

function renderInterrupts() {
  ui.interrupts.innerHTML = '';

  for (const interrupt of state.interrupts) {
    const card = document.createElement('div');
    card.className = 'interrupt-card inline-hitl';
    card.innerHTML = `<strong>${interrupt.kind}</strong><div>${interrupt.prompt}</div>`;
    if (interrupt.description) {
      const desc = document.createElement('div');
      desc.className = 'interrupt-desc';
      desc.textContent = interrupt.description;
      card.appendChild(desc);
    }
    if (interrupt.resultSummary) {
      const summary = document.createElement('div');
      summary.className = 'interrupt-result';
      summary.textContent = interrupt.resultSummary;
      card.appendChild(summary);
      ui.interrupts.appendChild(card);
      continue;
    }

    if (interrupt.kind === 'confirm') {
      const row = document.createElement('div');
      row.className = 'composer-actions';

      const approve = document.createElement('button');
      approve.textContent = '同意';
      approve.className = 'btn primary';
      approve.addEventListener('click', () => {
        void respondInterrupt(interrupt, true);
      });

      const reject = document.createElement('button');
      reject.className = 'btn ghost';
      reject.textContent = '拒绝';
      reject.addEventListener('click', () => {
        void respondInterrupt(interrupt, false);
      });

      row.append(approve, reject);
      card.appendChild(row);
    }

    if (interrupt.kind === 'single_select') {
      const row = document.createElement('div');
      row.className = 'composer-actions';
      for (const option of interrupt.options || []) {
        const choose = document.createElement('button');
        choose.className = 'btn ghost';
        choose.textContent = option.label || option.id || '选择';
        choose.addEventListener('click', () => {
          void respondInterrupt(interrupt, option.id ?? option.value ?? option.label ?? true);
        });
        row.appendChild(choose);
      }
      card.appendChild(row);
    }

    if (interrupt.kind === 'form') {
      const row = document.createElement('div');
      row.className = 'composer-actions';
      const submit = document.createElement('button');
      submit.className = 'btn primary';
      submit.textContent = '提交表单';
      submit.addEventListener('click', () => {
        void respondInterrupt(interrupt, { submitted: true });
      });
      row.appendChild(submit);
      card.appendChild(row);
    }

    ui.interrupts.appendChild(card);
  }
}

function openArtifactPreview(artifact) {
  if (!artifact) {
    return;
  }
  const artifactId = artifact.artifact_id || artifact.file_id || artifact.path || artifact.title;
  if (!artifactId) {
    return;
  }
  const existing = state.artifacts.find(item => item.artifact_id === artifactId);
  if (!existing) {
    state.artifacts.unshift({ ...artifact, artifact_id: artifactId });
  }
  state.previewArtifactId = artifactId;
  state.previewDiagramMode = 'rendered';
  state.rightPaneMode = 'preview';
  renderRightPane();
}

function closeArtifactPreview() {
  state.previewArtifactId = null;
  state.rightPaneMode = 'inspector';
  renderRightPane();
}

function renderRightPane() {
  if (!ui?.rightPane) {
    return;
  }

  if (state.rightPaneMode === 'preview' && state.previewArtifactId) {
    const artifact = state.artifacts.find(item => item.artifact_id === state.previewArtifactId);
    if (artifact) {
      const isDiagram = artifact.type === 'diagram';
      const isSourceMode = state.previewDiagramMode === 'source';
      const previewBody = isDiagram
        ? `
          <div class="mermaid-preview-mode">
            <button id="toggle-diagram-view" type="button" class="btn ghost">${isSourceMode ? '查看渲染' : '查看源码'}</button>
            <button id="copy-mermaid-source" type="button" class="btn ghost">复制源码</button>
          </div>
          ${isSourceMode
            ? `<pre class="mermaid-source">${artifact.preview_text || ''}</pre>`
            : `<div id="preview-mermaid-rendered" class="mermaid-rendered mermaid-rendered-pane"></div>`}
        `
        : `
          <div class="pane-path">${artifact.path || ''}</div>
          ${artifact.content ? `<pre class="pane-content">${escapeHtml(artifact.content)}</pre>` : ''}
        `;
      ui.rightPane.innerHTML = `
        <div class="pane-head">
          <strong>预览</strong>
          <button id="close-preview" class="btn ghost">关闭</button>
        </div>
        <div class="pane-block">
          <div class="pane-title">${artifact.title || artifact.artifact_id}</div>
          <div class="pane-meta">${artifact.type || 'file'}${artifact.mime_type ? ` · ${artifact.mime_type}` : ''}</div>
          ${previewBody}
        </div>
      `;
      const closeBtn = document.getElementById('close-preview');
      if (closeBtn) {
        closeBtn.addEventListener('click', () => closeArtifactPreview());
      }
      if (isDiagram) {
        const toggleBtn = document.getElementById('toggle-diagram-view');
        if (toggleBtn) {
          toggleBtn.addEventListener('click', () => {
            state.previewDiagramMode = state.previewDiagramMode === 'source' ? 'rendered' : 'source';
            renderRightPane();
          });
        }
        const copyBtn = document.getElementById('copy-mermaid-source');
        if (copyBtn) {
          copyBtn.addEventListener('click', async () => {
            try {
              await navigator.clipboard.writeText(String(artifact.preview_text || ''));
            } catch {
              // best effort
            }
          });
        }
        if (!isSourceMode) {
          const target = document.getElementById('preview-mermaid-rendered');
          void renderMermaidInto(target, String(artifact.preview_text || 'graph TD;A-->B'));
        }
      }
      return;
    }
  }

  state.rightPaneMode = 'inspector';
  const recent = state.artifacts.slice(0, 5);
  const artifactList = recent.length
    ? recent.map(item => `<button type="button" class="pane-link" data-artifact-id="${item.artifact_id}">${item.title || item.artifact_id}</button>`).join('')
    : '<div class="empty">暂无对象。</div>';

  ui.rightPane.innerHTML = `
    <div class="pane-head"><strong>检查器</strong></div>
    <div class="pane-block">
      <div class="pane-section-title">对象</div>
      ${artifactList}
    </div>
    <div class="pane-block">
      <div class="pane-section-title">状态</div>
      <div>运行：${state.runState}</div>
      <div>活动任务：${state.activeTaskCount}</div>
      <div>待处理交互：${state.pendingInterrupt ? '是' : '否'}</div>
    </div>
    <div class="pane-block">
      <div class="pane-section-title">技能</div>
      <div>${state.activeSkills.length ? state.activeSkills.join(', ') : '暂无激活技能。'}</div>
    </div>
    <details class="pane-details">
      <summary>更多</summary>
      <div>模式：${state.rightPaneMode}</div>
    </details>
  `;
  for (const btn of ui.rightPane.querySelectorAll('.pane-link')) {
    btn.addEventListener('click', () => {
      const artifact = state.artifacts.find(item => item.artifact_id === btn.dataset.artifactId);
      openArtifactPreview(artifact);
    });
  }
}

async function respondInterrupt(interrupt, value) {
  state.interrupts = state.interrupts.map(item => (
    item.interrupt_id === interrupt.interrupt_id
      ? { ...item, status: 'submitting' }
      : item
  ));
  renderInterrupts();
  try {
    await request(`/sessions/${interrupt.session_id}/interrupts/${interrupt.interrupt_id}/respond`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: interrupt.kind, value }),
    });
    state.interrupts = state.interrupts.map(item => (
      item.interrupt_id === interrupt.interrupt_id
        ? { ...item, status: 'resolved', resultSummary: `Resolved: ${String(value)}` }
        : item
    ));
    renderInterrupts();
  } catch (error) {
    state.interrupts = state.interrupts.map(item => (
      item.interrupt_id === interrupt.interrupt_id
        ? { ...item, status: 'pending' }
        : item
    ));
    renderSystemMessage(`Interrupt response failed: ${error.message}`);
    renderInterrupts();
  }
}

function bindUiHandlers() {
  ui.saveBase.addEventListener('click', () => {
    state.apiBase = ui.apiBase.value.trim().replace(/\/$/, '');
    persistApiBase(state.apiBase);
    void refreshSessions();
  });

  ui.newSession.addEventListener('click', async () => {
    const session = await createSession();
    await refreshSessions(session.session_id);
  });

  ui.deleteCurrentSession.addEventListener('click', () => {
    void deleteSession();
  });

  ui.sendMessage.addEventListener('click', () => {
    void sendCurrentMessage();
  });

  ui.composer.addEventListener('keydown', event => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void sendCurrentMessage();
    }
  });

  ui.fileInput.addEventListener('change', () => {
    void uploadSelectedFiles();
  });

  ui.imageViewerClose.addEventListener('click', () => {
    closeImageViewer();
  });

  ui.imageViewer.addEventListener('click', event => {
    if (event.target === ui.imageViewer) {
      closeImageViewer();
    }
  });

  window.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeImageViewer();
    }
  });
}

function bootstrap() {
  renderAppShell();
  ui = getUi();
  bindUiHandlers();
  updateStatusBar();
  renderRightPane();
  void refreshSessions();
}

try {
  bootstrap();
} catch (error) {
  renderFatalError(error);
}





