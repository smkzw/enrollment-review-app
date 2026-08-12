# Enrollment Review Project Instructions

## Current Phase

- The current rearchitecture task is in design and conference review.
- Do not implement the large rearchitecture until Codex presents the final design and the user approves continuation.
- Keep `docs/REARCHITECTURE_DISCOVERY_20260812.md`, `docs/PROJECT_CONTEXT.md`, and the active task/conference context as durable decision sources.

## Clinical And Evidence Boundaries

- Never modify source protocols, raw subject documents, manual IE trackers, or existing clinical reports.
- Legacy projects are read-only counterexample and regression anchors. New architecture work must create fresh projects from source inputs.
- Protocol and current amendment are authoritative. Q&A, letters, email, and medical interpretation may clarify ambiguity but cannot change or override the protocol/current amendment.
- Preserve official IN/EX numbering and parent/child logic. Do not hardcode project-specific clinical fixes into shared rules.
- Separate rule judgment from gap reason. Do not collapse record incompleteness, missing source file, unperformed procedure, professional judgment, conflict, OCR risk, or future-stage requirement into one status.
- Preserve source file, document version, page, exact excerpt, and image/text location for every material fact and rule assessment.
- The application is AI-led but is not the final enrollment decision authority. Every unresolved item needs a specific responsible party, action, acceptable evidence, due stage, and rule/source locator.

## Product Boundaries

- Target: local single-Mac, single-user, direct launch without login or multi-account ownership behavior.
- Support immutable full evidence snapshots and deduplicated incremental uploads.
- Later-stage evidence must not silently rewrite an earlier-stage result.
- Use source-preserving OCR/fact correction with affected-scope reruns and history.
- Design Patient Profile as the source-linked longitudinal view from earliest evidence through the current prescreen/screen/baseline cutoff.

## Engineering And Verification

- Prefer structured domain models and deterministic validators for logic, dates, units, state, and audit behavior. Use bounded Agents only for semantic tasks.
- Use `apply_patch` for manual text/code edits. Preserve unrelated user changes.
- Verify user-facing UI in a real browser at representative desktop and narrow viewports.
- Keep visual layouts responsive; avoid fixed pixel dimensions as the primary layout strategy.
- Update task context and `docs/PROJECT_CONTEXT.md` at material milestones.

## Conference Boundary

- Conference participants are read-only advisers. They must not modify source or application files and must not read raw clinical material outside this workspace.
- Codex owns final synthesis, clinical/product acceptance, and user delivery.
