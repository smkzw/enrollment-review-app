# Conference Context: rv1006-whole-temporal-restriction-review-20261008

Created: 2026-10-08 08:21:33 CST
Objective: Challenge exact whole-unit temporal restriction, source-heading coverage, and safe saved-result reuse without clinical adoption or repeated source reads
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

- Linked execution task: `rv1006-whole-temporal-restriction-review-20261008`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen code, base1796417d plus the current scoped patch: `app/services/protocol_control_restricted_source.py` (complete); `app/services/protocol_control_execution.py` (identity1960-2035, partial source2500-2675, preflight2750-2930, execution3500-3740); `app/protocols/protocol_control_gate.py` (source helpers4910-4995 and restricted scope5101-5220); `tests/v2/services/test_protocol_control_execution.py` (synthetic restriction examples155-780, saved consumers930-1160). Read only this set, no private clinical sources, databases, env, or histories. At most16 purposeful reads/searches; return explicit limits, do not run tests or shell.
- Actual owner-only frozen evidence: a product batch passed source/author gates, retained18 source points and4 candidates, then failed typed TEMPORAL_SCOPE_UNRESOLVED at point9; a distinct point14 stayed genuinely unresolved. Source point9 includes action+time_validity and a separately sourced local heading; its five-point unit and the other five-point unit share candidate/context dependencies. The patch preserves both entire units non-executable, with ten exact points and zero surviving candidates in this batch; other source units retain existing dispositions. Actual read-only current gate passes this derived output; it is not publication, global dependency closure, or clinical acceptance.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: challenge whole-unit restriction and coverage of exact local headings; dangerous negative cases and actual saved/declaration consumers. Advise the smallest legal zero-reread recovery for a failed saved result when only restriction-consumer implementation changes: current partial-source identity discards wire on compiler changes, and current preserved proof only accepts SOURCE_TARGET_REVIEW_UNRESOLVED, not typed temporal failure. Do not suggest version whitelists or copying a success checkpoint.
- Out of scope: clinical judgment, permitting executable unknowns, removing dependency guards, redesigning orchestration/cache systems, new models, or any file edit. Connected synthetic regressions are running and have failures still under owner diagnosis; do not claim green or acceptance.

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

- 2026-10-08 08:21:33 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
