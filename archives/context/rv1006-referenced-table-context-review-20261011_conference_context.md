# Conference Context: rv1006-referenced-table-context-review-20261011

Created: 2026-10-11 18:30:02 CST
Objective: 只读评审冻结的原文明确表号上下文闭合：真实物理表身份、同号歧义、non_control只读准入、旧计划恢复和提示消费；不读临床、不改代码、不运行产品或测试
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `rv1006-referenced-table-context-review-20261011`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen base HEAD a201d040 plus current patch in app/domain/contracts/source_table_references.py, app/domain/contracts/protocol_controls.py, app/protocols/protocol_control_planning.py, app/protocols/phase_applicability_planning.py and tests/v2/protocols/test_protocol_control_generalization.py. Inspect those diffs and complete affected definitions only.
- Read-only adjacent source if needed: app/services/protocol_control_execution.py (_same_deep_batch_material, closure and reuse checks), app/agents/protocol_control_source_interpretation.py (source prompt contextual units). Do not read clinical/tmp/data/env files, private answers or other workers' reports. No writes or tests or provider calls.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: exact explicit numbered table reference -> unique physical table rows/title in readonly context. Existing table number/key helpers extracted unchanged into a pure shared helper. Related-context mapping is reused; non_control context admitted only if physically tied to the explicitly cited table. No ownership/disposition change. Actual source contained a known table reference whose body was omitted from its batch.
- Out of scope: clinical phase/meaning determination, formal adoption, signatures, global model changes, numeric repair, new framework or database. Incomplete/ambiguous reference must not be guessed.
- Challenge duplicate number tables, title/body spoofing, foreign document/coordinate aliases, missing rows, misleading punctuation, stale batches and consumer prompt visibility. Does validation introduce a circular source proof from only the included context? Does the server reconstruct/verify the true frozen plan, or could a fabricated subset get accepted? Give a concrete affected path rather than generalized warnings.
- Owner is performing synthetic connected tests and read-only actual plan comparison; these are not clinical acceptance. No new Job has been started. Recommend the smallest coherent fix if a real boundary failure exists.

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

- 2026-10-11 18:30:02 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
