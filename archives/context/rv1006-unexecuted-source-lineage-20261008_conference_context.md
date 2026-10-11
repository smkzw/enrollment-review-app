# Conference Context: rv1006-unexecuted-source-lineage-20261008

Created: 2026-10-08 11:43:34 CST
Objective: Challenge frozen per-step upstream reuse for unexecuted queued siblings after terminal interruption; no clinical adoption or history rewrite
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

- Linked execution task: `rv1006-unexecuted-source-lineage-20261008`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen base be9903dd; current owner patch in app/services/protocol_control_execution.py and tests/v2/services/test_protocol_control_execution.py only.
- Read complete affected definitions: _resolve_unexecuted_deep_source (2778-2827), _preflight_deep_source (2830-3120), _validated_deep_source (3355-3438), and _execute_deep reuse branch (3784-3939). Use narrow symbol lookup if line offsets changed.
- Read the new six-case test at 2834-2935 and its actual existing JobStore/JobRunner helpers as needed.
- Runtime evidence supplied by owner: latest isolated Job 640780a62e2f450b9cfa8a1b53d51b1c failed_final, six calls 237.8054817s, valid 18-point source saved; first author repair invalid. Steps 2-11 remain queued here but frozen reuse points to ten actual completed checkpoints in bb59749aa7c047c1bb90f43e97a3c285. Step 12 has four valid partial siblings, not a completed batch. These counts are not clinical acceptance.
- Do not read runtime directories, clinical originals, databases or environment files. Synthetic tests are source evidence, not proof they passed.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: provenance integrity, scope/identity compatibility, preflight/execution symmetry, actual root checkpoint validation, cancellation and history preservation, attribution of reused results. Challenge normal usability and dangerous counterexamples.
- Out of scope: editing, running tests or model calls, reading clinical data, arbitrary history search, clinical adoption, browser acceptance. At most 12 bounded file reads and two scoped searches. Tools stay enabled.

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

- 2026-10-08 11:43:34 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
