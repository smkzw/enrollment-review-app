# Conference Context: rv1006-unresolved-sibling-retention-20261007

Created: 2026-10-07 15:13:57 CST
Objective: Review frozen bounded ordering change: preserve gate-verified independent source inserts without accepting unresolved siblings or invalid same-unit semantics; no clinical inputs or edits.
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

- Linked execution task: `rv1006-unresolved-sibling-retention-20261007`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- app/agents/protocol_control_deconstructor.py
- app/agents/protocol_control_source_interpretation.py
- app/agents/protocol_control_stage_compiler.py
- app/services/protocol_control_restricted_source.py
- tests/v2/protocols/test_slice58c_control_deconstructor.py
- app/services/protocol_control_execution.py
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: frozen two-file patch against fe8826e9. Read the working diff and the source-target block, insert assembler, checkpoint serialization, and restricted consumer. The initial target review is fully validated before any insert. Move unresolved stopping after independent bounded inserts/alignment, preserve remaining full review and coverage; no final output with unresolved siblings. Version existing recovery policy v3 to v4 (repair identity only). Focused synthetic checks:23 passed,511 deselected/1.30s,not final integration acceptance.
- Out of scope: no clinical data, database, private tmp, .env, model endpoints, browser, web, source edits or test execution. Use read-only tools for declared source definitions and relevant synthetic tests; no broad repo or history scan. Maximum18 material read/search/diff calls; if further evidence needed return precise limitation rather than exceed. Owner performs final tests and clinical decisions.
- Uncertainty: can ordering expose invalid inserts, discard unresolved review, return final output, or reuse unresolved scope as approval? Can same-unit syntactic separation be mistaken for semantic independence? It remains only an unaccepted checkpoint, not qualified restricted publication. Restricted eligibility is unchanged.

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

- 2026-10-07 15:13:57 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
