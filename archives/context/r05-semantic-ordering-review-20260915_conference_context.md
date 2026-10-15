# Conference Context: r05-semantic-ordering-review-20260915

Created: 2026-09-15 13:11:19 CST
Objective: Read-only source review of semantic latest/earliest integration, candidate accounting, source scope and version-bound adoption; no runtime or staged tests
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> codex-subagent/codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-semantic-ordering-20260915`
- Execution evidence status: pi/cursor/default selector only, exact backing model unknown; cannot assert full model independence. Reviewer fresh source context, no worker report/private rationale supplied.
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Current frozen source scope: app/services/semantic_observation_selection.py; app/services/ordered_observation_selection.py; app/services/qualified_binding_selection.py; app/domain/contracts/qualified_binding_selection.py; app/domain/contracts/control_evaluation_spec.py; app/domain/contracts/observation_selection.py; app/services/predicate_proposition_calculation.py; app/domain/proposition_observations.py; app/projections/control_operand_calculation.py; app/projections/control_calculation_experiment.py; app/services/qualified_proposition_evidence.py; app/agents/protocol_control_deconstructor.py relevant version/schema/prompt; app/services/frozen_review_calculation.py version/integration. Read adjacent definitions as necessary, not broad history.
- Requirements: newest explicit source single latest/earliest selection applies deterministic and semantic; no source or date guessing; same-day/partial ambiguity unresolved; all supplied candidate pairs/fields must be accounted and content qualified before date choice. This is supplied input, not proof all clinical history. Select before/after time window only per explicit policy. Nonselected source relations remain frozen evidence/audit, not used or false unresolved. Source scope and researcher judgment remain separate prerequisites. Version changes cannot authorize old results. User forbids staged tests until product built; source-only checks allowed.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: concrete code risks and integration gaps, exact file/lines, minimal remedies; check semantic override/rejection handling, date qualification when no time constraint, all candidates coverage, sorting audit vs selected pairs, unresolved retained source, versions/history. Independently challenge any false acceptance or valid-input rejection; do not insist on unverifiable clinical completeness from enumerated data.
- Out of scope: source writes, recursive workers, personal configuration/memory, product model/API/DB/browser calls, tests/imports, final clinical/visual acceptance. No manual gold answers. Return PASS/FAIL/UNVERIFIED scoped to source review, not product readiness.

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

- 2026-09-15 13:11:19 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
