# Worker 03 Same-Session Visual Remediation

Continue the existing worker_03 session. Do not create a new route or change provider/model. Read the current workspace state and the original assignment before editing.

## Hard boundaries

- Work only inside the runner-controlled current workspace `.`.
- Read these files only as the mandatory starting set: `AGENTS.md`, `context/enrollment_phase1_frontend_execution_context.md`, `plans/codex_execution_enrollment_phase1_frontend.md`, `prompts/execution/enrollment_phase1_frontend/worker_03.md`, and the Phase 1 frontend files needed to diagnose the listed defects. Additional reads must be directly justified by a listed defect.
- Write only Phase 1 frontend and e2e files needed for the listed defects. Do not modify fixture clinical truth, Phase 0.5 contracts, legacy application code, or production data.
- Return exactly one runner-managed report file: `runs/execution/enrollment_phase1_frontend/worker_03.md`. Do not write it directly; return the complete report in the final assistant response for the runner to persist.

Codex has completed an initial visual review of the generated screenshots. The implementation is functionally broad, but the following user-visible defects block Phase 1 acceptance. Fix the shared causes, add deterministic regressions, regenerate screenshots, and rerun the full unit/build/e2e suite.

## User and language contract

- The target user is a Chinese-speaking senior clinical-trial medical monitor who is visually sensitive, not interested in implementation details, and should see priority clinical work before system mechanics.
- All visible labels must be native Chinese clinical-workflow language. Do not expose fixture identifiers, backend terms, schema names, Gate, stub, log, or pure-English project labels.
- Do not change clinical decision rules, fixture clinical truth, or Phase 0.5 contracts. A display-only label may be derived in the shell.

## Blocking visual defects

1. Narrow top bar at 390 px is unreadable: `当前位置` wraps vertically, project/version text truncates, and help becomes vertical. On narrow screens, show only the menu icon, current page title, and a compact help icon/button with an accessible Chinese label. Hide or move project/version context out of the narrow top bar; do not merely shrink text. On desktop keep useful context, but render a Chinese display label such as `界面试用项目 · III期` and `方案 V1.0`; never show `SYNTHETIC-001-III` in the visible UI.
2. Narrow `受试者与资料` puts the full subject list before the selected Patient Profile. Replace the narrow side list with a compact subject selector or collapsible picker so the selected subject profile and its risk-focused content are visible in the first screen. Desktop may keep the side list.
3. Narrow `行动中心` has state/blocking badges overlapping the action summary. Use a responsive single-column row/card arrangement with code, summary, metadata, and status in stable separate positions. Add an overlap-oriented browser assertion. The desktop page should select the first visible action by default when no URL action is specified, so the user immediately sees why/what/who/evidence details.
4. `今日工作` currently exposes many repetitive action rows. Present a short, priority-first preview (no more than six visible rows) and an explicit Chinese link showing that more items are available in `行动中心`. Do not discard or mutate the underlying action collection.
5. Patient Profile desktop event cards are too tall for sparse content. Compact the event presentation into denser timeline rows while preserving evidence links, risk labels, and readable touch targets.

## Regression evidence

- Extend unit tests for display-only project naming, default action selection, action preview cap, and narrow subject picker behavior.
- Extend Playwright checks at 390 px to prove: current page title is readable on one line; no raw `SYNTHETIC-001-III`; selected Patient Profile content is reachable without scrolling through the full subject list; action summary and status boxes do not overlap; no page-level horizontal overflow.
- Keep existing desktop, zoom, keyboard, evidence-path, and axe checks passing.
- Regenerate the full screenshot set. Inspect the specific 390 px screenshots after generation and report the observed visual result, not only test status.

## Boundaries

- This is a same-session repair. Do not fall back to another model because of latency.
- Keep edits within the Phase 1 frontend and e2e files. Cross-slice edits are allowed only for these tested shared defects and must be recorded.
- Do not add dependencies.
- Return the complete execution report schema used in the first pass, with changed files, exact checks, screenshot paths, and any residual uncertainty.
