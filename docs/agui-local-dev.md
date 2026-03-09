# AGUI Local Development

## Backend

Start the AGUI-compatible backend:

```bash
nanobot web --host 127.0.0.1 --port 8000
```

## Frontend

Serve the static browser client:

```bash
cd apps/agui-web
python serve.py --host 127.0.0.1 --port 4173
```

Then open `http://127.0.0.1:4173` and set the backend base URL to `http://127.0.0.1:8000`.

## Event Model v2 (Web Projection)

Canonical families supported by the current AGUI projection layer:

- `message.*` (`message.started`, `message.delta`, `message.completed`)
- `tool.*` (`tool.started`, `tool.completed`, `tool.failed`)
- `artifact.*` (`artifact.created`, `artifact.updated`, `artifact.referenced`)
- `task.*` (`task.started`, `task.updated`, `task.completed`, `task.failed`)
- `interrupt.*` (`interrupt.requested`, `interrupt.resolved`)
- `error`

Notes:

- Legacy `run.started` is still emitted for compatibility during transition.
- Transcript-facing tool payloads include summary and preview fields.

## Artifact Types and Preview

Supported artifact types:

- `file`
- `code`
- `image`
- `link`
- `diagram`
- `report`

Preview endpoint:

```bash
GET /artifacts/{artifact_id}
```

Preview payload includes `viewer_type`; diagram previews also include `view_modes` with rendered/source support.

## Supported Interrupt Kinds

- `confirm`
- `single_select`
- `form`

Inline HITL cards are rendered in transcript and keep a result summary after submit.

## Right Pane States

The right pane has only two primary states:

- `Inspector` (default): minimal sections for Artifacts, Status, Skills, and collapsed Details.
- `Preview`: focused artifact preview; closing preview returns to Inspector.

## Upload Semantics

- **Image uploads** keep multimodal semantics and can be passed as image media.
- **Non-image uploads** are path-first for runtime use (`mode=path`), rather than forcing raw blob content into prompts.

## Mermaid Behavior

- Mermaid artifacts render inline in transcript.
- Users can copy Mermaid source directly from the transcript.
- Preview pane supports rendered/source viewing modes for diagram artifacts.

## Verification Commands

Run focused AGUI workspace checks:

```bash
python -m pytest tests/test_web_event_model_v2.py tests/test_artifact_model.py tests/test_artifact_events.py tests/test_tool_event_projection.py tests/test_artifact_preview_api.py tests/test_runtime_upload_semantics.py tests/test_interrupts.py tests/test_task_projection.py tests/test_agui_web_frontend.py -v
```

Run AGUI regression subset:

```bash
python -m pytest tests/test_web_api_smoke.py tests/test_web_files.py tests/test_interrupts.py tests/test_agui_web_frontend.py -v
```

## Manual API Smoke

```bash
curl -X POST http://127.0.0.1:8000/sessions -H "Content-Type: application/json" -d "{}"
```

```bash
curl -N http://127.0.0.1:8000/sessions/<session_id>/events
```
