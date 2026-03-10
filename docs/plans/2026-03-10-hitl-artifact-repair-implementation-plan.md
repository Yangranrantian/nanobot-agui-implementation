# HITL And Artifact Preview Repair Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Repair the current Codex-style web workspace so that human-in-the-loop cards are truly anchored inside transcript messages and artifact/path references reliably open the right-side preview pane.

**Architecture:** Keep the existing AGUI MVP and Codex-style workspace structure, but correct message anchoring and artifact projection semantics. Move from composer-level interrupt rendering to message-level interrupt rendering, and make explicit artifact objects the primary preview path with regex path enhancement only as fallback.

**Tech Stack:** Existing Python backend (`nanobot/web/*`), existing browser client (`apps/agui-web`), SSE events, artifact preview API, transcript renderer, inline interrupt cards.

---

### Task 1: Capture the actual current behavior in a repair baseline

**Files:**
- Read: `apps/agui-web/src/app.js`
- Read: `nanobot/web/runtime.py`
- Read: `nanobot/web/models.py`
- Read: `tests/test_agui_web_frontend.py`
- Read: `tests/test_interrupts.py`
- Read: `tests/test_workspace_preview_api.py`
- Create: `docs/plans/2026-03-10-hitl-artifact-repair-baseline.md`

**Step 1: Write the baseline note**

Document the actual current behavior, including:

- interrupts render in `#interrupts` instead of inside messages
- `form` interrupts do not render real fields
- right-pane preview exists
- explicit artifacts and regex path fallback are mixed
- preview routing is partially working but not uniformly explicit

**Step 2: Verify current tests**

Run:

```bash
pytest tests/test_agui_web_frontend.py tests/test_interrupts.py tests/test_workspace_preview_api.py -v
```

Expected: PASS, while still not proving the target UX is correct

**Step 3: Commit**

```bash
git add docs/plans/2026-03-10-hitl-artifact-repair-baseline.md
git commit -m "docs: capture hitl and artifact repair baseline"
```

### Task 2: Add explicit interrupt anchoring in backend event payloads

**Files:**
- Modify: `nanobot/web/interrupts.py`
- Modify: `nanobot/web/runtime.py`
- Modify: `nanobot/web/models.py`
- Test: `tests/test_interrupts.py`

**Step 1: Write the failing test**

```python
def test_interrupt_request_includes_anchor_message_id():
    from nanobot.web.interrupts import InterruptEnvelope
    envelope = InterruptEnvelope(
        interrupt_id="int_1",
        session_id="sess_1",
        kind="confirm",
        prompt="Approve command?",
        anchor_message_id="msg_1",
    )
    assert envelope.anchor_message_id == "msg_1"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interrupts.py -v`
Expected: FAIL because anchor message identity is missing from interrupt payloads

**Step 3: Write minimal implementation**

Add `anchor_message_id` to interrupt envelope/request flow. Ensure `interrupt.requested` emits enough data for the frontend to mount the card inside a specific assistant message.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_interrupts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add nanobot/web/interrupts.py nanobot/web/runtime.py nanobot/web/models.py tests/test_interrupts.py
git commit -m "feat: anchor interrupts to assistant messages"
```

### Task 3: Project interrupts into message-level frontend state

**Files:**
- Modify: `apps/agui-web/src/app.js`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add a test that asserts interrupt cards are associated with transcript messages rather than the standalone `#interrupts` container.

Suggested assertion direction:

- do not rely on a global interrupt rail as the primary rendering target
- interrupt state attaches to a message model or message ID map

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_agui_web_frontend.py -v`
Expected: FAIL because interrupts are currently rendered globally

**Step 3: Write minimal implementation**

Refactor frontend state so interrupt cards are stored against the relevant assistant message. Keep `pendingInterrupt` only as a summary indicator if needed, not as the primary render source.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/agui-web/src/app.js tests/test_agui_web_frontend.py
git commit -m "feat: bind interrupts to transcript messages"
```

### Task 4: Render interrupt cards inside the relevant assistant message block

**Files:**
- Modify: `apps/agui-web/src/app.js`
- Modify: `apps/agui-web/src/styles.css`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add a test asserting that the transcript renderer places HITL card markup within the message rendering path rather than in the composer wrapper.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_agui_web_frontend.py -v`
Expected: FAIL because cards are currently mounted into `#interrupts`

**Step 3: Write minimal implementation**

Update message rendering so:

- assistant text renders first
- inline interrupt card renders inside the same message block
- resolved card remains there as result summary

Remove the dedicated `#interrupts` rendering path as the primary UI.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/agui-web/src/app.js apps/agui-web/src/styles.css tests/test_agui_web_frontend.py
git commit -m "feat: render hitl cards inline in transcript"
```

### Task 5: Replace placeholder form interrupts with real field rendering

**Files:**
- Modify: `apps/agui-web/src/app.js`
- Modify: `apps/agui-web/src/styles.css`
- Modify: `nanobot/web/interrupts.py`
- Test: `tests/test_interrupts.py`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add tests asserting:

- form interrupts render fields from payload
- submitted values are structured
- resolved form cards show a summary

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interrupts.py tests/test_agui_web_frontend.py -v`
Expected: FAIL because `form` is currently only a placeholder submit button

**Step 3: Write minimal implementation**

Support at least:

- text input
- textarea
- single-select field
- checkbox field

Submission must send structured field values instead of `{ submitted: true }`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_interrupts.py tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/agui-web/src/app.js apps/agui-web/src/styles.css nanobot/web/interrupts.py tests/test_interrupts.py tests/test_agui_web_frontend.py
git commit -m "feat: implement real form interrupts"
```

### Task 6: Upgrade confirm interrupts for command/tool approval UX

**Files:**
- Modify: `nanobot/web/interrupts.py`
- Modify: `nanobot/web/models.py`
- Modify: `apps/agui-web/src/app.js`
- Test: `tests/test_interrupts.py`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add tests asserting confirm payloads can include:

- `title`
- `description`
- `action_preview`
- `context_artifact_ids`

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_interrupts.py tests/test_agui_web_frontend.py -v`
Expected: FAIL because confirm prompts are still minimal

**Step 3: Write minimal implementation**

Upgrade confirm cards so they can support Codex-style “Should I run this?” UX with richer explanatory context.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_interrupts.py tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add nanobot/web/interrupts.py nanobot/web/models.py apps/agui-web/src/app.js tests/test_interrupts.py tests/test_agui_web_frontend.py
git commit -m "feat: enrich confirm interrupt cards"
```

### Task 7: Make explicit artifact references the primary preview path

**Files:**
- Modify: `nanobot/web/runtime.py`
- Modify: `nanobot/web/models.py`
- Modify: `apps/agui-web/src/app.js`
- Test: `tests/test_workspace_preview_api.py`
- Create: `tests/test_artifact_reference_priority.py`

**Step 1: Write the failing test**

```python
def test_explicit_artifact_reference_takes_priority_over_regex_fallback():
    artifact = {"artifact_id": "art_1", "type": "file", "path": "docs/spec.md"}
    assert artifact["artifact_id"] == "art_1"
```

Then add a frontend-facing test that explicit artifact references open preview directly without depending on inline path extraction.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workspace_preview_api.py tests/test_artifact_reference_priority.py -v`
Expected: FAIL because artifact and regex paths are still mixed without clear priority

**Step 3: Write minimal implementation**

Ensure transcript rendering prefers explicit `artifact_id`-backed references. Keep regex path enhancement only as fallback when explicit artifact data is missing.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workspace_preview_api.py tests/test_artifact_reference_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add nanobot/web/runtime.py nanobot/web/models.py apps/agui-web/src/app.js tests/test_workspace_preview_api.py tests/test_artifact_reference_priority.py
git commit -m "feat: prioritize explicit artifact references"
```

### Task 8: Normalize transcript object clicks to a single preview entrypoint

**Files:**
- Modify: `apps/agui-web/src/app.js`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add a test asserting that file/path/link/image/diagram transcript interactions all route through `openArtifactPreview(...)` semantics rather than divergent preview logic.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_agui_web_frontend.py -v`
Expected: FAIL because some interactions still rely on specialized or inferred behavior

**Step 3: Write minimal implementation**

Consolidate click handlers so all previewable transcript objects resolve or synthesize an artifact, then call one preview entrypoint.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/agui-web/src/app.js tests/test_agui_web_frontend.py
git commit -m "refactor: unify preview entrypoints"
```

### Task 9: Strengthen path fallback without letting it dominate the model

**Files:**
- Modify: `apps/agui-web/src/app.js`
- Modify: `nanobot/web/runtime.py`
- Test: `tests/test_workspace_preview_api.py`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add tests asserting:

- inline path fallback still works when no explicit artifact exists
- fallback preview does not override an existing artifact-backed object

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py -v`
Expected: FAIL because fallback and explicit paths are not yet clearly separated

**Step 3: Write minimal implementation**

Keep regex path enhancement as a backup feature only. Ensure it creates temporary artifacts consistently and does not compete with explicit artifacts.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/agui-web/src/app.js nanobot/web/runtime.py tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py
git commit -m "fix: constrain path fallback to backup preview flow"
```

### Task 10: Improve preview failure handling and in-place recovery

**Files:**
- Modify: `apps/agui-web/src/app.js`
- Modify: `apps/agui-web/src/styles.css`
- Modify: `nanobot/web/api.py`
- Test: `tests/test_workspace_preview_api.py`
- Test: `tests/test_agui_web_frontend.py`

**Step 1: Write the failing test**

Add tests asserting:

- preview failure shows a lightweight user-visible error
- current transcript remains stable
- closing preview returns to inspector

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py -v`
Expected: FAIL because preview errors are not yet product-grade

**Step 3: Write minimal implementation**

Handle missing or invalid preview targets gracefully. Do not leave the pane in a broken state or silently do nothing.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add apps/agui-web/src/app.js apps/agui-web/src/styles.css nanobot/web/api.py tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py
git commit -m "fix: harden preview failure ux"
```

### Task 11: Add behavior-oriented regression tests for transcript-anchored HITL

**Files:**
- Modify: `tests/test_agui_web_frontend.py`
- Modify: `tests/test_interrupts.py`

**Step 1: Replace weak static assertions where needed**

Add stronger tests for:

- interrupt card anchored in transcript message render path
- resolved interrupt summary staying in place
- form field rendering and submission structure

**Step 2: Run tests to verify they fail before final implementation adjustments**

Run: `pytest tests/test_agui_web_frontend.py tests/test_interrupts.py -v`
Expected: FAIL until the behavior is truly implemented

**Step 3: Adjust implementation only as needed**

Make the smallest changes required to satisfy real behavior assertions.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agui_web_frontend.py tests/test_interrupts.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_agui_web_frontend.py tests/test_interrupts.py
git commit -m "test: strengthen hitl behavior coverage"
```

### Task 12: Add behavior-oriented regression tests for artifact-driven preview

**Files:**
- Modify: `tests/test_agui_web_frontend.py`
- Modify: `tests/test_workspace_preview_api.py`
- Modify or create: `tests/test_artifact_reference_priority.py`

**Step 1: Add stronger tests**

Cover:

- explicit artifact click opens preview
- fallback path click opens preview when no artifact exists
- diagram artifact opens rendered/source preview path
- preview close returns to inspector

**Step 2: Run tests to verify they fail if behavior is incomplete**

Run: `pytest tests/test_agui_web_frontend.py tests/test_workspace_preview_api.py tests/test_artifact_reference_priority.py -v`
Expected: FAIL until the interaction model is correct

**Step 3: Adjust implementation only as needed**

Patch the smallest amount of backend/frontend code required to satisfy the behavior contract.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agui_web_frontend.py tests/test_workspace_preview_api.py tests/test_artifact_reference_priority.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_agui_web_frontend.py tests/test_workspace_preview_api.py tests/test_artifact_reference_priority.py
git commit -m "test: strengthen artifact preview behavior coverage"
```

### Task 13: Update docs to reflect repaired semantics

**Files:**
- Modify: `docs/agui-local-dev.md`
- Modify: `README.md`
- Create or modify: `docs/plans/2026-03-10-hitl-artifact-repair-baseline.md`
- Reference: `docs/plans/2026-03-10-hitl-artifact-repair-design.md`
- Reference: `docs/plans/2026-03-10-hitl-artifact-repair-implementation-plan.md`

**Step 1: Update behavior docs**

Document:

- interrupt cards are transcript-anchored
- form interrupts now collect real structured values
- preview prefers explicit artifact references
- path regex enhancement is fallback only

**Step 2: Run targeted verification**

Run:

```bash
pytest tests/test_interrupts.py tests/test_workspace_preview_api.py tests/test_agui_web_frontend.py -v
```

Expected: PASS

**Step 3: Run broader related verification**

Run:

```bash
pytest tests/test_web_api_smoke.py tests/test_web_events.py tests/test_web_files.py tests/test_agui_web_frontend.py tests/test_interrupts.py tests/test_workspace_preview_api.py -v
```

Expected: PASS

**Step 4: Final verification**

Run:

```bash
pytest -q
```

Expected: PASS or only documented unrelated failures remain

**Step 5: Commit**

```bash
git add README.md docs/agui-local-dev.md docs/plans/2026-03-10-hitl-artifact-repair-design.md docs/plans/2026-03-10-hitl-artifact-repair-implementation-plan.md
git commit -m "docs: describe repaired hitl and artifact preview flows"
```
