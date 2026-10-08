# Conference Context: rv1006-source-review-pending-input-20261008

Created: 2026-10-08 10:51:08 CST
Objective: Review frozen source-target pending-input propagation and invalid-review classification; no clinical adoption or new recovery framework
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `rv1006-source-review-pending-input-20261008`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen patch against HEAD03be2eb1: app/agents/protocol_control_source_interpretation.py:1225-1415 and1460-1525; app/services/protocol_control_restricted_source.py:319-358 and720-774; app/services/protocol_control_execution.py:3890-4015.
- Synthetic source/tests: tests/v2/protocols/test_slice58c_control_deconstructor.py:3900-3965; tests/v2/services/test_protocol_control_execution.py:370-437 and the complete test_invalid_target_review_keeps_technical_failure_and_persists_actual_answer definition (locate with rg, read only that definition).
- Real runtime redacted observation: latest isolated Job completed eleven deep groups, then failed at12. Source inventory retained an unresolved dimension. Both initial target review and one focused correction claimed full coverage; frozen validator rejected them. Recovery retains four other review items, not a complete five-item review. No raw clinical files/DB/prompt receipts are in the review scope.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: Does exposing frozen unresolved data prevent a hidden-input contradiction without changing clinical meaning? Does early refusal of invalid-review restriction preserve valid R1 results and technical failure classification? Check whether any result can now be incorrectly adopted, and advise identity treatment for repaired input packets under unchanged validator/policy semantics.
- Out of scope: raw clinical data, other files, writes, tests/model calls, browser, source deletion, new framework, semantic resolution of the actual clinical statement. At most ten bounded file reads; if more needed, identify precise missing definition rather than scan the repository. No edit, no private reasoning required.

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

- 2026-10-08 10:51:08 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
