# Conference Context: enrollment_phase2_acceptance

Created: 2026-08-14 10:44:34
Objective: 以真实医学监查员与独立工程审查者视角，验收Phase 2 SQLite领域持久化、任务恢复、接口中文表达及Phase 1.5界面无回归，明确区分已实现与未实现能力
Task type: `visual_delivery_conference`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

    - Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route. The Codex subAgent Luna route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
    - Other complex tasks use a Codex-chaired panel with no sub-venue chair. Participant 1 is Pi/Alibaba `qwen3.8-max` (xhigh) -> Pi/OpenCode Go `deepseek-v4-flash` (max) during the Beijing 22:00-07:00 window; daytime is Pi/CMS-SMK `deepseek-v4-flash` (max) -> Pi/OpenCode Go `deepseek-v4-flash` (max). Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority. The explicit Luna native/CLI compatibility route remains available for execution roles that declare Codex subAgent.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `AGENTS.md` and `.trellis/tasks/08-14-phase2-sqlite-domain-jobs/{prd,design,implement}.md`.
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`, `docs/PROJECT_CONTEXT.md`.
- Current branch source under `app/storage`, `app/workflow`, `app/services`, `app/api/v2`, `frontend/src/api`, and tests under `tests/v2` / `frontend`.
- Execution manager report `runs/execution/enrollment_phase2_sqlite/manager.md` and actual local runtime at `http://127.0.0.1:4173` (Phase 1.5 synthetic UI) and `http://127.0.0.1:8912/openapi.json` (Phase 2 API).
- Do not read raw clinical source material outside this workspace. Legacy project data is a read-only regression anchor and is not needed for this Phase 2 review.

## Scope

- In scope: SQLite schema/constraints, migration backup and rollback, canonical payload/hash, repository scope integrity, idempotency, revision conflicts, stale scope, Job/Step/Checkpoint/Event, leases and recovery, API/SSE semantics, Chinese user-facing errors, and regression/visual honesty of the existing synthetic UI.
- Out of scope: real protocol parsing, upload/OCR, fact extraction, Patient Journey generation, LLM eligibility review, real clinical project creation, and security testing. These belong to later phases and must not be inferred from a clickable synthetic screen.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- Each participant uses a fresh context, independently reproduces material behavior where practical, and returns findings ordered by severity with file/line or runtime evidence.
- A pass requires no silent history overwrite, no permanent processing state, no duplicate execution after lease recovery, no ambiguous UTC API timestamps, and no UI claim that later-phase clinical capabilities are real.

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-08-14 10:44:34: Conference initialized by `hermes_workflow_guard.py init-conference`.
