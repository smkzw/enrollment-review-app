# Conference Context: r05-retest-design-20260915

Created: 2026-09-15 14:38:38 CST
Objective: Source-grounded design for conditional clinical retest relation and consumption within existing product architecture; not a new framework, no runtime or staged tests
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

- Linked execution task: `r05-retest-design-20260915`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section17.2, plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md T3, app/domain/contracts/observation_selection.py, app/domain/contracts/control_evaluation_spec.py, app/domain/contracts/rules.py related predicates/time fields; app/services/ordered_observation_selection.py, semantic_observation_selection.py; app/services/proposition_evidence_input.py, proposition_evidence_job.py, proposition_evidence_receipts.py; app/llm/proposition_context.py and proposition_evidence.py; app/services/qualified_binding_selection.py and predicate_proposition_calculation.py. Read adjacent source definitions only to verify reuse.
- User requirements: protocol determines permitted retest triggers, count/permission/time limit and whether replaces initial or combines; never infer initial/retest relation from chronology. Use models for source meaning, code for numbers/dates/logic; independent dual product VLM, versioned outputs and receipts, no new automatic adoption. No disease/drug/protocol-specific rules, no staged tests until entire system built. Existing source policy latest/earliest and single/any/all do not by themselves express conditional retest. Preserve raw evidence and initial review histories.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: propose smallest complete change using existing explicit observation policy and persistent dual evidence task mechanisms. Identify EXACT integration files/classes for protocol capture, source closure, fact candidate grouping, dual relationship proof, deterministic trigger/permission/time evaluation, result selection, frozen report/action. Distinguish existing support vs missing. Prefer shared submodule, do not put hundreds of lines in giant files. Consider whether existing control applicability/trigger/exception can represent permission without duplicating full predicate algebra; no circular ObservationPolicy->rules dependency. Bound supported generic forms but preserve unsupported source, don't force source simplification. Include same-day, repeated attempt, bad initial sample vs true abnormal result, discretionary investigator permission, unrelated simultaneous tests, missing date/source, additional repeat after max, missing permitted repeat. Do not assume absence of repeat violates OPTIONAL permission. Propose field shape and order with minimal counterexamples; source reasoning only.
- Out of scope: implementation, tests/import/runtime, external medical claims, external network, source clinical file reads, parallel agents, modifying model routes or clinical approval. User source requirements are authority; recommendations advisory only.

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

- 2026-09-15 14:38:38 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
