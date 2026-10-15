# Conference Context: phase4-wp44c-final-acceptance

Created: 2026-08-21 01:53:30
Objective: 独立验收 Phase 4 Slice 4.4 WP-44C 后端接口与事务语义，决定是否解锁 WP-44D
Task type: `code_open_audit`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route, then Codex subAgent Luna (max). The Codex subAgent route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/CMS-SMK `deepseek-v4-flash` (max) -> Pi/OpenCode Go `gpt-5.6-luna` (max) -> Kimi Code `k3-256k` (high). Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `AGENTS.md`, the active Trellis task PRD/design/implement files, and `research/slice44-detailed-contract-review.md`.
- WP-44C implementation and deterministic V2 tests in this isolated worktree.
- No production database or raw clinical material.

## Scope

- In scope: independent acceptance of WP-44C API contracts, current-pointer authority, idempotency, transaction rollback, referenced-document resolution boundaries and application-error ownership.
- Out of scope: frontend WP-44D, Slice 4.5 source-document scrolling/red-box experience, production writes and clinical decision logic.

## Success Criteria

- A fresh-context verifier reproduces material negative paths and runs deterministic regression anchors.
- No open P0/P1/P2 remains; current-pair reactivation does not add history; referenced-document resolution cannot cross scope or leave the current snapshot; API errors do not depend on storage exception types.
- No production path is read or modified; Codex retains final acceptance.

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

- 2026-08-21 01:53:30: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-21: Native fresh-context `gpt-5.6-sol:high` verifier returned `REJECT` with three P1 findings.
- 2026-08-21: Codex repaired shared boundaries and completed full V2/static verification.
- 2026-08-21: Same verifier session independently rechecked and returned `ACCEPT`; no open P0/P1/P2. WP-44D unlocked.
