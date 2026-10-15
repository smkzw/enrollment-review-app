# Conference Context: enrollment-visual-input-review-20260916

Created: 2026-09-16 20:59:08 CST
Objective: Read-only review of current product page-reader input design after six isolated MTPLX effort comparisons. Inspect artifacts/mtplx-dual-basic-20260916/effort-comparison-v17/REVIEW.md, app/llm/page_review_harness.py, app/evidence/render.py, app/domain/contracts/page_review.py and clause_pack.py. Recommend the smallest source-preserving orientation or compact-input change, with explicit provenance/coordinate mapping, model independence, acceptance limits, and no clinical auto-accept changes. Challenge assumptions: no new model calls, no external raw records, no code edits, no gold injection, no reset of two-round business budget. Distinguish proved failures from hypotheses; assess current lifecycle diagnostic changes in app/llm/mtplx_owned_server.py and app/services/page_review_job_executor.py for adjacent defects. Only write the declared review report; cite source file lines. Do not delegate.
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-visual-input-review-20260916`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read the objective's named source files and their directly imported contracts. The comparison REVIEW.md is the owner's bounded observation, not independent clinical proof. Raw original image and saved outputs under that same experiment root may be read only if necessary; no clinical data outside this worktree.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: source-level input design, source-preserving orientation identity, coordinate mapping, compact input without lost requirements, lifecycle diagnostics.
- Out of scope: source edits, inference calls, final clinical acceptance, changes to provider configuration, personal harness configuration, delegation.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Conference Pass Rule

This packet uses one serial Codex-led conference object. Each declared role receives one complete prompt and may use multiple internal tool turns. Codex decides whether a same-session follow-up is needed after reviewing the result; follow-ups do not create a new conference or change the route identity.

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

- 2026-09-16 20:59:08 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
