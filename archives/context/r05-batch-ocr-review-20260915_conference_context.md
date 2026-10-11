# Conference Context: r05-batch-ocr-review-20260915

Created: 2026-09-15 05:54:44 CST
Objective: 只读核对批量重新识别的版本保留、幂等、取消恢复及前端衔接，不运行阶段测试或产品模型
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/zcode/glm-5.3:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-batch-ocr-20260915`
- Execution evidence status: `linked`
- Excluded route identities: `codebuddy/codebuddy-cli/deepseek-v4.1-flash`, `zcode/zcode/glm-5.3-flash`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Current source: app/services/batch_evidence_reprocessing.py, batch_evidence_reprocessing_view.py, evidence_reprocessing.py; app/api/v2/batch_evidence_reprocessing.py and app.py integration; frontend/src/api/evidence/reprocessingBatches.ts, components/review/BatchOcrPanel.tsx, pages/ReviewProjectPage.tsx, pages/EvidencePage.tsx changed reprocessed-view definitions. Read adjacent JobStore/runner/source repositories as required. Design section17 and recovery Plan T5 govern immutable source and explicit activation.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: read-only full affected definitions, source lifecycle defects with exact file:line and minimal repairs. Own batch members only, frozen payload/profile, sequential child-terminal wait without holding model lease, honest failed child outcomes, explicit original/new result distinction, replay/cancel/retry/race recovery and current-vs-recorded UI status. No silent fallback to other model or current source.
- Out of scope: any edits, tests, app/DB/model/browser execution, clinical files, credentials, other checkout, delegation, web research. User defers staged tests to full build. Report is advisory, not runtime or clinical acceptance. Do not read worker's persuasive report; current source is the artifact.

Owner source integration already corrected: intake now creates/checks idempotent parent in BEGIN IMMEDIATE before freshness/pending checks, rolls new parent back if invalid; owned child checks project and derived namespace; view reuses single-result verification so native-text no-op is not new revision; source result deep link chooses exact requested old snapshot, not silently current. Child failed retry is rejected when its parent was explicitly stopped. Check these independently; do not assume correct.

Return actual P0/P1/P2, no invented completeness from compilation. Check unknown/corrupt members cannot starve other cancellation, parent completed cannot conceal missing child or checkpoint, selected old/new result cannot target wrong candidate. UI wide desktop only. No new clinical interpretation needed.

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

- 2026-09-15 05:54:44 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
