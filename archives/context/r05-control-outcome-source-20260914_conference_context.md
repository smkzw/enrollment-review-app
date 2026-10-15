# Conference Context: r05-control-outcome-source-20260914

Created: 2026-09-14 14:22:28 CST
Objective: Read-only source review of frozen control outcome projection and unresolved official predicates; challenge modality, branch attribution, unknown vs missing, source identity and formal publication boundaries. No tests or product calls.
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

- Linked execution task: `r05-control-outcome-source-20260914`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md sections17.1.1-17.3, plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md T5. A completed audit may contain unresolved clinical items, but an incomplete implementation cannot claim completion. Do not fabricate IN/EX codes for controls. No final enrollment decision is being implemented here.
- Frozen source: app/projections/control_review_outcome.py, app/projections/control_calculation_experiment.py, app/domain/control_layer_evaluation.py, app/domain/contracts/control_evaluation_spec.py, app/domain/contracts/protocol_controls.py; official changes app/domain/expression.py evaluate_component, app/domain/gates/assessment.py derive_gate_gap_types, app/services/component_review.py and app/services/frozen_review_calculation.py. Read adjacent exact definitions as needed, not the giant historical logs.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: challenge new pure control outcome projection and unresolved official-predicate input. Audit source identity, group activation, modality, uncertainty, missing-vs-unverified and sibling attribution. Give concrete defects and precise corrective suggestions with files/lines. Specifically assess whether projection can misstate fulfillment or hide a valid record. No confidence-based acceptance.
- Out of scope: any edits, recursive delegation, conference spawning, model/product API calls, DB access, env or personal configuration, application imports, tests, browser, installation, external browsing. Read only inside this worktree; output report via runner. No source file modification. The source set will remain unchanged during your review.

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

- 2026-09-14 14:22:28 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
