# Conference Context: r05-batch-estimates-design-20260915

Created: 2026-09-15 06:16:50 CST
Objective: 只读审阅现有正式批量审核和OCR记录，提出最小、证据约束的耗时与费用估算接入方案；不得模型调用、数据库、应用、测试或改代码。
Task type: `C03`
Risk: `medium`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/zcode/glm-5.3:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-batch-estimates-design-20260915`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- docs/REARCHITECTURE_FINAL_DESIGN_20260812.md: batch preflight estimates from historical median, labelled estimates.
- app/services/batch_review_workflow.py, batch_review_view.py, prepared_review_workflow.py, batch_evidence_reprocessing.py; app/storage/models.py; app/workflow/jobstore.py; app/domain/contracts/page_review.py; frontend/src/components/review/BatchReviewPanel.tsx. Follow narrow source dependencies only.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: Identify existing trustworthy time and cost receipts and compatibility identities; propose minimal API/service/UI changes. How to avoid mixing model/effort/prompt/schema/cache/size/stage or treating unknown fees as zero? Can completed workflow wall time be estimated honestly including queue/retry? Give concrete fields/functions and missing measurement points. No broad architecture rewrite.
- Out of scope: All writes, raw clinical data, env/credentials, DB reads, imports/application execution, tests, browser, network and product model calls. Do not infer actual historical metrics from source definitions. This is engineering source advice, not product evaluation. User defers tests until full construction.

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

- 2026-09-15 06:16:50 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
