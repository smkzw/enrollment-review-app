# Conference Context: rv1006-source-stage-boundary-review-20261008

Created: 2026-10-08 12:51:24 CST
Objective: 只读审查两个源范围阻断的最小修复位置：不强求异时OR分支共同阶段，既有原生访视列证据如何合法传递；保留完整覆盖及真实歧义，不放宽采用或重复整方案
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

- Linked execution task: `rv1006-source-stage-boundary-review-20261008`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen code HEAD 8acd30c7; only owner current implement documentation dirty, seven inherited delivery documents excluded. No product source changes pending.
- Read complete affected definitions, not entire large files. At most eight substantive reads, no tests, model calls, private data or changes. Allowed source: app/agents/protocol_control_source_interpretation.py (SourceStatement, source/scope/review prompts and validators); app/protocols/procedure_catalog.py (schedule_row_values/schedule_column_scope); app/services/protocol_control_execution.py (preflight, source seed proof, current identity checks); app/services/protocol_control_restricted_source.py (restricted batch/whole unit); app/domain/contracts/protocol_controls.py (restricted source/known targets); app/services/eligibility_review_projection.py (restricted projections); relevant narrow tests/v2/protocols/test_slice58c_control_deconstructor.py examples. Search within these paths allowed.
- Clinical raw material is not given to this engineering reviewer. Two synthetic analogues: (1) a source requirement says 'previous condition A, or a positive condition B during screening'. Both temporal branches explicit, no single common affected_stage. Existing source reader retains a question merely because there is no common stage; target reviewer cannot legally clear saved source.unresolved. (2) an X is in a frozen native table cell at column 2. Source includes all original member paths, context rows contain stage/visit/week/day at column 2. schedule_column_scope gives grounded header refs and baseline, but source quote alone has no stage; a scope correction borrowing stage without source reference is rejected. Empty possible_cell_scope_labels is only same-cell label metadata, not absence of column headers. Do not turn these analogues into disease-specific code.
- Actual product diagnostic used unchanged existing prompt/endpoint in two fresh isolated sessions: source 12 valid five statements but same temporal question; source 17 rejected SOURCE_STAGE_UNGROUNDED. No DB write/adoption. These are observations, not a determination that source meaning is complete.

## Scope

- In scope: challenge minimal legal repair positions and effects on current consumers/cache identity. Compare source-level clarification, grounded native-header propagation, and faithful restrictions; identify unsupported shortcut risks. Recommend one smallest complete path, exact functions and positive/adversarial consumer checks.
- Out of scope: edits, tests, private clinical files, new framework, new model, full reruns, clinically approving a source or loosening adoption. Do not regex-match Chinese unresolved reasons to drive recovery. Do not assume no common stage equals genuine ambiguity, or coordinate alignment equals valid timing. Current default workflow and complete publication gate retained.
- Owner concern to challenge: changing global source prompt identity forces rereading all fifteen completed groups; merely changing the validator can preserve successful groups but cannot masquerade the new prompt as old. Can the existing scoped correction/recovery legally solve the issue, or is a narrowly scoped intake/material contract necessary? SourceScopeCorrection currently preserves source.unresolved; blindly clearing it is not authorized. A faithful official duplicate restriction must actually constrain the official consumer, not only add a supplemental warning.

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

- 2026-10-08 12:51:24 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
