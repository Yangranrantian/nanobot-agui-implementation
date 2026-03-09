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
  lastEventAt: null,
  isSending: false,
  isUploading: false,
  fileStatus: 'No files selected',
};

const app = document.getElementById('app');
let ui;

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

  app.innerHTML = `
    <div class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <div class="brand-kicker">Nanobot AGUI</div>
          <h1>Webchat</h1>
        </div>

        <div class="api-config">
          <label for="api-base">Backend</label>
          <div class="api-row">
            <input id="api-base" value="${state.apiBase}" />
            <button id="save-base" class="btn ghost">Save</button>
          </div>
        </div>

        <div class="sidebar-actions">
          <button id="new-session" class="btn primary">New chat</button>
          <button id="delete-current-session" class="btn ghost danger">Delete current</button>
        </div>

        <div class="sessions-head">Sessions</div>
        <div id="session-list" class="session-list"></div>
      </aside>

      <main class="chat-panel">
        <header class="chat-header">
          <div class="chat-title-wrap">
            <div class="chat-kicker">Current session</div>
            <h2 id="session-title">No session selected</h2>
          </div>
          <div class="status-bar">
            <span id="connection-chip" class="chip">Offline</span>
            <span id="run-chip" class="chip">Idle</span>
            <span id="last-event" class="chip muted">No events yet</span>
          </div>
        </header>

        <section id="transcript" class="transcript">
          <div class="empty">Create or select a session to start.</div>
        </section>

        <section class="composer-wrap">
          <div id="interrupts" class="interrupts"></div>
          <div id="attachments" class="attachments"></div>
          <textarea id="composer" placeholder="Send a message... Enter to send, Shift+Enter for new line"></textarea>
          <div class="composer-actions">
            <input id="file-input" type="file" multiple hidden />
            <label for="file-input" id="file-picker" class="btn ghost file-picker">Choose files</label>
            <span id="file-status" class="file-status">No files selected</span>
            <button id="send-message" class="btn primary">Send</button>
          </div>
        </section>
      </main>

      <aside id="right-pane" class="right-pane"></aside>

      <div id="image-viewer" class="image-viewer hidden" role="dialog" aria-modal="true">
        <button id="image-viewer-close" class="btn ghost image-viewer-close">Close</button>
        <img id="image-viewer-img" class="image-viewer-img" alt="preview" />
      </div>
    </div>
  `;
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

  ui.connectionChip.textContent = state.connectionStatus === 'online' ? 'Connected' : 'Disconnected';
  ui.connectionChip.className = `chip ${state.connectionStatus === 'online' ? 'ok' : 'warn'}`;

  const runLabel = state.runState === 'running'
    ? 'Thinking...'
    : state.isUploading
      ? 'Uploading files...'
      : state.isSending
        ? 'Sending...'
        : 'Idle';

  ui.runChip.textContent = runLabel;
  ui.runChip.className = `chip ${state.runState === 'running' || state.isSending || state.isUploading ? 'busy' : ''}`;
  ui.lastEvent.textContent = state.lastEventAt
    ? `Last event ${new Date(state.lastEventAt).toLocaleTimeString()}`
    : 'No events yet';

  ui.sendMessage.disabled = state.isSending || state.isUploading;
  ui.sendMessage.textContent = state.isUploading ? 'Uploading...' : state.isSending ? 'Sending...' : 'Send';
  ui.fileStatus.textContent = state.fileStatus;
  ui.filePicker.classList.toggle('disabled', state.isUploading || state.isSending);
}

function setConnectionStatus(status) {
  state.connectionStatus = status;
  updateStatusBar();
}

function setRunState(nextState) {
  state.runState = nextState;
  state.lastEventAt = Date.now();
  updateStatusBar();
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
  return (items || []).map((item, index) => ({
    id: `history-${index}`,
    role: item.role === 'assistant' ? 'assistant' : item.role === 'system' ? 'system' : 'user',
    content: normalizeMessageContent(item.content),
    attachments: normalizeMessageAttachments(item.attachments),
  }));
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
    renderSystemMessage(`Failed to load sessions: ${error.message}`);
    setConnectionStatus('offline');
  }
}

function renderSessions() {
  ui.sessionList.innerHTML = '';

  if (state.sessions.length === 0) {
    ui.sessionList.innerHTML = '<div class="empty">No sessions yet.</div>';
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
    renderSystemMessage(`Delete session failed: ${error.message}`);
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

  for (let i = 0; i < attempts; i += 1) {
    try {
      const history = await request(`/sessions/${sessionId}/messages`);
      const mapped = toUiMessages(history.items);
      if (mapped.length > 0) {
        state.messages = mapped;
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
    renderSystemMessage(`Failed to load message history: ${error.message}`);
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

  ['run.started', 'message.started', 'message.delta', 'message.completed', 'tool.started', 'tool.completed', 'tool.failed', 'task.started', 'task.updated', 'task.completed', 'task.failed', 'interrupt.requested', 'interrupt.resolved', 'error'].forEach(name => {
    source.addEventListener(name, event => {
      setConnectionStatus('online');
      state.lastEventAt = Date.now();
      updateStatusBar();
      handleEvent(JSON.parse(event.data));
    });
  });

  source.onerror = () => {
    setConnectionStatus('offline');
    renderSystemMessage('Event stream disconnected.');
  };
}

function handleEvent(event) {
  switch (event.type) {
    case 'run.started':
      setRunState('running');
      break;

    case 'message.started':
      setRunState('running');
      state.pendingAssistantId = `assistant-${Date.now()}`;
      state.messages.push({ id: state.pendingAssistantId, role: 'assistant', content: '...', attachments: [] });
      renderTranscript();
      break;

    case 'message.delta':
      appendAssistantChunk(event.content || '', false);
      break;

    case 'message.completed':
      if (typeof event.content === 'string' && event.content.length > 0) {
        appendAssistantChunk(event.content, true);
      }
      state.pendingAssistantId = null;
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
      upsertToolEvent(event);
      renderTranscript();
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
      setRunState('idle');
      renderSystemMessage(`Error: ${event.message || 'unknown error'}`);
      break;

    default:
      break;
  }
}

function appendAssistantChunk(chunk, replace = false) {
  let target = state.messages.find(message => message.id === state.pendingAssistantId);

  if (!target) {
    target = { id: `assistant-${Date.now()}`, role: 'assistant', content: '', attachments: [] };
    state.messages.push(target);
    state.pendingAssistantId = target.id;
  }

  target.content = replace ? chunk : `${target.content}${chunk}`;
  renderTranscript();
}

function upsertToolEvent(event) {
  state.toolEvents.push(event);
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
  const title = attachment.title || attachment.filename || attachment.artifact_id || 'Mermaid Diagram';
  block.innerHTML = `
    <div class="mermaid-head">
      <strong>${title}</strong>
      <div class="mermaid-actions">
        <button type="button" class="btn ghost mermaid-copy">Copy Source</button>
        <button type="button" class="btn ghost mermaid-open">Open in Preview</button>
      </div>
    </div>
    <pre class="mermaid-source">${source}</pre>
  `;
  const copyBtn = block.querySelector('.mermaid-copy');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(source);
      } catch {
        // best effort copy
      }
    });
  }
  const openBtn = block.querySelector('.mermaid-open');
  if (openBtn) {
    openBtn.addEventListener('click', () => {
      openArtifactPreview({
        artifact_id: attachment.artifact_id || attachment.file_id || title,
        type: 'diagram',
        title,
        path: attachment.path,
        mime_type: attachment.mime_type || 'text/plain',
        preview_text: source,
      });
    });
  }
  return block;
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
    ui.transcript.innerHTML = '<div class="empty">No messages yet.</div>';
    return;
  }

  for (const message of state.messages) {
    const div = document.createElement('div');
    div.className = `message ${message.role}`;

    const body = document.createElement('div');
    body.className = 'message-body';
    body.textContent = cleanImagePlaceholder(message.content, message.attachments);
    div.appendChild(body);

    renderMessageAttachments(div, normalizeMessageAttachments(message.attachments));
    ui.transcript.appendChild(div);
  }

  renderToolFlow(ui.transcript);

  ui.transcript.scrollTop = ui.transcript.scrollHeight;
}

function renderToolFlow(container) {
  if (!state.toolEvents.length) {
    return;
  }
  const wrap = document.createElement('div');
  wrap.className = 'tool-flow';
  for (const item of state.toolEvents) {
    const payload = item.payload || {};
    const details = document.createElement('details');
    details.className = 'tool-flow-item';
    details.open = false;
    const summary = document.createElement('summary');
    summary.textContent = payload.summary || payload.tool_name || item.type;
    details.appendChild(summary);

    const detail = document.createElement('div');
    detail.className = 'tool-flow-detail';
    detail.textContent = JSON.stringify(
      {
        type: item.type,
        tool_call_id: payload.tool_call_id,
        tool_name: payload.tool_name,
        arguments_preview: payload.arguments_preview,
        result_preview: payload.result_preview,
        duration_ms: payload.duration_ms,
      },
      null,
      2
    );
    details.appendChild(detail);
    wrap.appendChild(details);
  }
  container.appendChild(wrap);
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
  state.messages.push({ id: `user-${Date.now()}`, role: 'user', content, attachments: sentAttachments });
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
    state.fileStatus = 'No files selected';
    renderAttachments();
    updateStatusBar();
  } catch (error) {
    renderSystemMessage(`Send failed: ${error.message}`);
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
  state.fileStatus = `Uploading ${files.length} file(s)...`;
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
  state.fileStatus = state.attachments.length > 0 ? `${state.attachments.length} file(s) ready` : 'No files selected';
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
      approve.textContent = 'Approve';
      approve.className = 'btn primary';
      approve.addEventListener('click', () => {
        void respondInterrupt(interrupt, true);
      });

      const reject = document.createElement('button');
      reject.className = 'btn ghost';
      reject.textContent = 'Reject';
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
        choose.textContent = option.label || option.id || 'Choose';
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
      submit.textContent = 'Submit form';
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
      const previewBody = isDiagram
        ? `
          <div class="mermaid-preview-mode">
            <button type="button" class="btn ghost">Rendered</button>
            <button type="button" class="btn ghost">Source</button>
          </div>
          <pre class="mermaid-source">${artifact.preview_text || ''}</pre>
        `
        : `<div class="pane-path">${artifact.path || ''}</div>`;
      ui.rightPane.innerHTML = `
        <div class="pane-head">
          <strong>Preview</strong>
          <button id="close-preview" class="btn ghost">Close</button>
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
      return;
    }
  }

  state.rightPaneMode = 'inspector';
  const recent = state.artifacts.slice(0, 5);
  const artifactList = recent.length
    ? recent.map(item => `<button type="button" class="pane-link" data-artifact-id="${item.artifact_id}">${item.title || item.artifact_id}</button>`).join('')
    : '<div class="empty">No artifacts yet.</div>';

  ui.rightPane.innerHTML = `
    <div class="pane-head"><strong>Inspector</strong></div>
    <div class="pane-block">
      <div class="pane-section-title">Artifacts</div>
      ${artifactList}
    </div>
    <div class="pane-block">
      <div class="pane-section-title">Status</div>
      <div>Run: ${state.runState}</div>
      <div>Active tasks: ${state.activeTaskCount}</div>
      <div>Pending interrupt: ${state.pendingInterrupt ? 'yes' : 'no'}</div>
    </div>
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





