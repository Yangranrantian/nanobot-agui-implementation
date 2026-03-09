# AGUI MVP Baseline Audit (2026-03-09)

This note captures the verified baseline state on branch `codex/agui-implementation` before Codex-style workspace upgrades.

## 1) Current session API shape

From `nanobot/web/api.py` + `nanobot/web/models.py`:

- `POST /sessions` -> `SessionSummary`
- `GET /sessions` -> `SessionListResponse`
- `DELETE /sessions/{session_id}` -> delete status
- `GET /sessions/{session_id}/messages` -> `MessageListResponse`
- `POST /sessions/{session_id}/messages` -> `RunAcceptedResponse` (`202`)
- `GET /sessions/{session_id}/events` -> SSE stream (`encode_sse`)
- `POST /sessions/{session_id}/interrupts/{interrupt_id}/respond` -> `InterruptResolvedResponse`
- `POST /files` -> `FileUploadResponse`
- `GET /files/{file_id}` -> raw file download/preview response

Observed response schemas:

- `MessageRecord` has `role`, `content`, `timestamp`, `attachments`.
- `SendMessageRequest` includes `content` plus opaque `attachments`.
- `FileUploadResponse` currently only contains:
  - `file_id`
  - `filename`
  - `mime_type`
  - `size_bytes`
  - `path`

No explicit Event Model v2 envelope model exists in shared schema files.

## 2) Current event shape

From `nanobot/web/events.py` + `nanobot/web/runtime.py`:

- Event helper is `make_event(event_type, **payload)` and returns a flat dict:
  - `{ "type": "<event_type>", ...payload_fields }`
- SSE frame uses:
  - `event: <type>`
  - `data: <json_of_full_event>`

Currently observed families in web runtime / frontend listeners:

- `run.started`
- `message.started`
- `message.delta`
- `message.completed`
- `interrupt.requested`
- `interrupt.resolved`
- `model.switched` (runtime-only helper signal)
- `error`

Missing from baseline:

- Canonical v2 envelope fields (`session_id`, `run_id`, `timestamp`, `payload`) enforced uniformly
- `tool.*`
- `artifact.*`
- `task.*`
- richer interrupt lifecycle (`cancelled`, `expired`)

## 3) Current interrupt payloads

From `nanobot/web/interrupts.py` + runtime flow:

- Request model:
  - `kind`
  - `prompt`
  - `options` (list)
  - `fields` (list)
- Runtime envelope adds:
  - `interrupt_id`
  - `session_id`
- Resolve response model:
  - `kind`
  - `value`
- Resolution API response:
  - `status`
  - `session_id`
  - `interrupt_id`

Frontend behavior currently handles a primitive inline `confirm` card (approve/reject). Other card kinds are not product-grade.

## 4) Current frontend transcript rendering behavior

From `apps/agui-web/src/app.js` + `styles.css`:

- Transcript is simple message bubbles (`user`, `assistant`, `system`).
- Assistant streaming is handled by `message.started/delta/completed`.
- Tool activity is not projected into transcript as Codex-style gray collapsible execution blocks.
- No artifact-first rendering abstraction in transcript.
- Attachments are rendered as:
  - image thumbnail with modal viewer
  - plain file badges
- Right pane dual-state model does not exist; current UI is a two-column layout (session list + chat panel), with image modal overlay only.

## 5) Current file upload behavior

From `nanobot/web/files.py`, `nanobot/web/runtime.py`, and frontend upload flow:

- Backend stores uploads under `web_uploads` using `<file_id>_<filename>`.
- Upload API returns basic file metadata (`FileUploadResponse`).
- Frontend stores returned metadata directly into `attachments`.
- Runtime resolves `media_paths` only for image-like attachments and passes only those paths to agent `media=...`.
- Non-image files are uploaded and referenced in message metadata, but there is no explicit artifact model or artifact event emission.
- Path-first semantics for non-image files are only implicit and not formalized as artifact contracts.

## 6) Current Mermaid support behavior

- No Mermaid-specific artifact type.
- No inline Mermaid renderer in transcript.
- No "copy source" affordance for Mermaid.
- No right-pane rendered/source dual view for diagrams.
- Mermaid content is effectively treated as normal message text/code.

## 7) Baseline gaps against Codex-style workspace design

Confirmed missing capabilities:

1. No Event Model v2 projection (`message.*`, `tool.*`, `artifact.*`, `task.*`, `interrupt.*`, `error`) with canonical envelope.
2. No shared artifact-first transcript/preview model.
3. No right-pane dual state (`Inspector` vs `Preview`).
4. No product-grade inline HITL cards and post-submit summary UX.

Additional observed gaps relevant to implementation order:

- No transcript-level quiet tool flow grouping/collapse behavior.
- No blue-highlighted clickable local path/URL artifact references.
- No typed artifact preview resolver API.

## 8) Baseline execution environment note

- Repo baseline requires `Python >=3.11` (`pyproject.toml`), but machine default `python` points to `3.7.4`.
- Running baseline regression with system Python fails at collection (PEP585 typing syntax and import path side effects).
- Baseline verification is reproducibly green when executed with project venv Python 3.11:
  - `.venv\Scripts\python.exe -m pytest ...`
