# HITL And Artifact Preview Repair Design

**Goal:** Repair the two product-critical gaps in the Codex-style web workspace implementation: true in-transcript human-in-the-loop interactions and a stable artifact/path-to-preview interaction model.

**Scope:** This phase is corrective. It does not add major new product surfaces. It fixes interaction semantics so the current workspace behaves as intended.

## Why This Phase Exists

Code review of the current `codex/agui-implementation` worktree shows that the implementation is partially correct but still misses two core interaction goals:

1. Interrupt cards exist, but they are rendered in a fixed composer-adjacent region instead of being anchored inside the relevant assistant message.
2. Right-side preview exists, but artifact and path preview entry points are inconsistent. Some objects preview correctly, some rely on path-regex fallback, and some referenced files do not reliably become previewable artifacts.

This phase exists to make those two flows behave like a coherent Codex-style product.

## Product Goals

### Goal 1: True inline HITL

Human-in-the-loop should feel like part of the same assistant reply and the same run.

Expected user experience:

- assistant explains why input is needed
- an interrupt card appears directly inside that assistant message block
- the user answers there
- the card collapses into a structured result summary
- execution continues in the same transcript position

### Goal 2: Stable artifact preview

Any important referenced object in the conversation should be previewable with a single, predictable interaction model:

- blue-highlighted path or link
- clickable code/file/report reference
- clickable image thumbnail
- clickable Mermaid diagram block
- click opens right-side preview
- close returns to the minimal inspector

## Design Principles

1. No floating interrupt UI. HITL belongs to the transcript, not the composer shell.
2. Preview is object-driven, not regex-driven. Fallback parsing may exist, but explicit artifact objects should be the main path.
3. One preview entrypoint. All clickable objects should route through a common `openArtifactPreview(...)` behavior.
4. Preserve narrative continuity. Interruption and preview should not make the transcript feel fragmented.
5. Prefer explicit linkage over inferred state. Interrupts should be anchored to message identity; artifact references should prefer artifact identity.

## Problem 1: Current HITL Rendering Is Not In-Transcript

The current implementation renders interrupts into a dedicated `#interrupts` container inside the composer area. That makes them inline on the page, but not inline in the message stream.

Consequences:

- cards are visually detached from the assistant message that requested them
- resolved state is not preserved in the original transcript position
- multiple runs can feel ambiguous when interrupts accumulate
- the UI does not match Codex-style execution continuity

## HITL Repair Design

### Transcript anchoring

Each interrupt must be associated with a specific assistant message.

Preferred backend field:

- `anchor_message_id`

If backend change is too invasive, front-end state may temporarily anchor the interrupt to the currently active assistant message at the time of `interrupt.requested`, but the durable target design should still be explicit anchoring.

### Rendering model

Interrupt cards should render inside the relevant assistant message block, after the assistant explanation text and before later continuation.

Each interrupt card should support these states:

- `pending`
- `submitting`
- `resolved`
- `cancelled`
- `expired`

After resolution, the card must not disappear. It should render as a compact result summary inside the same message.

### Card types

This repair phase should preserve the existing types but make them truly usable:

- `confirm`
- `single_select`
- `form`

`multi_select` can remain optional if it is not already wired.

### Form repair

The current form implementation is only a placeholder submit action. This phase must render real fields from interrupt metadata and submit structured values.

Supported field types for this phase:

- `text`
- `textarea`
- `single_select`
- `checkbox`

### Confirm repair

For tool-execution confirmation, the interrupt payload should support richer descriptive fields:

- `title`
- `description`
- `action_preview`
- `context_artifact_ids`

That allows the UI to resemble Codex-style approval cards rather than plain `confirm / Approve?` prompts.

## Problem 2: Artifact Preview Entry Is Inconsistent

The current implementation mixes:

- explicit artifacts from events
- uploaded artifacts
- Mermaid-derived artifacts
- regex-based inline path detection
- direct `/workspace/preview` probing

This works for some cases but is not stable enough for product use.

## Artifact Repair Design

### Primary interaction path

The primary path should be:

runtime or event projection
-> artifact object created or referenced
-> transcript renders a clickable artifact reference
-> click opens preview

### Fallback interaction path

Regex-based path enhancement can remain, but only as a fallback when an explicit artifact was not produced.

### Unified artifact identity

Every clickable object should have a stable `artifact_id` before opening preview whenever possible.

Sources include:

- uploaded files
- generated files
- workspace file references
- links
- diagrams
- reports

### Viewer strategy

Right-pane preview should continue to support:

- file/report text preview
- code preview
- image preview
- link summary preview
- Mermaid rendered/source preview

But opening preview should not depend on ad-hoc reconstruction of temporary objects unless fallback mode is active.

### Path-first semantics

Non-image uploads and local file references should prioritize path semantics for the runtime and artifact semantics for the UI.

The same object should be:

- a path-addressable runtime reference
- a previewable UI artifact

## Minimal UI State Changes

The frontend state should explicitly support:

- messages with embedded interrupt state
- artifact references linked to message content
- preview selection by `artifact_id`
- a fallback path-preview cache that is secondary, not primary

Recommended additions or normalization:

- `message.interrupts` or `message.interruptCard`
- `message.artifactRefs`
- `artifactIndexById`
- `pendingInterruptByMessageId`

## Testing Requirements

Static string-presence tests are not sufficient for this repair phase.

The new tests should verify behavior, not just implementation markers.

Required categories:

1. Transcript-level interrupt anchoring
2. Interrupt resolution leaving summary in-place
3. Form fields rendering from payload and submitting structured data
4. Clicking a transcript artifact opening right-pane preview
5. Explicit artifact events taking precedence over regex fallback
6. Path fallback still working when no explicit artifact exists

## Out Of Scope

This phase should not introduce:

- new task dashboards
- multi-tab preview
- new orchestration systems
- collaborative review workflows
- large inspector redesign

## Success Criteria

This repair phase succeeds if:

- interrupt cards render inside the relevant assistant message
- resolved interrupts remain as result summaries in the transcript
- form interrupts collect real field values
- file/path/link/code/diagram references open right-pane preview consistently
- explicit artifact objects drive most preview behavior, with regex fallback only as backup
