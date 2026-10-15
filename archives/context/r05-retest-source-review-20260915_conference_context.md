# Conference Context: r05-retest-source-review-20260915

Created: 2026-09-15 15:53:59 CST
Objective: 只读审阅条件复查的通用来源合同及双族解构接线，核对来源、历史身份和未实现消费边界，不改文件不运行测试
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

- Linked execution task: `r05-retest-source-review-20260915`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Current original requirements: protocol governs whether repeats are required, optional, forbidden or discretionary; retain triggers, limits, scope, result-use and exact source. Chronology alone never proves repeat relation or permission. No default latest/best result, invented dates/counts, project/disease/model-specific fixes. Existing historical identities remain readable. New source contract alone is not a completed repeat evaluator.
- Read complete relevant definitions in: app/domain/contracts/repeat_scheme.py; app/domain/contracts/rules.py; app/domain/contracts/control_evaluation_spec.py; app/agents/protocol_deconstructor.py; app/agents/protocol_control_deconstructor.py; app/protocols/deconstruction_gate.py; app/protocols/protocol_control_gate.py; app/services/protocol_control_execution.py; app/domain/expression.py; app/domain/gates/assessment.py; app/services/qualified_binding_selection.py; app/domain/contracts/qualified_binding_selection.py; app/services/frozen_review_calculation.py; app/projections/control_operand_calculation.py; frontend/src/domain/reviewConditionNotes.ts.
- Authoritative background, targeted sections only: docs/REARCHITECTURE_FINAL_DESIGN_20260812.md and plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md. Do not read previous conference opinions. Follow imports to adjacent source definitions only if needed to prove a finding.

## Scope

- In scope: source-level review of repeat source capture, both deconstruction producers, JSON schema/wire versions, source lineage, historical identity and fail-closed consumer guard. Locate high-impact defects with file/line evidence. Distinguish this bounded increment from the pending relation/permission/result-selection implementation.
- Out of scope: ALL writes, tests, imports or execution of application code, model calls, database access, browser/server startup, network, personal histories/configuration, recursive delegation, clinical acceptance. Only read/search/stat/git diff commands. Never git checkout/reset/clean. Return the report in your final answer; runner persists it.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- Only listed source and necessary adjacent definitions are read; no files are modified. Codex retains final acceptance.

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

- 2026-09-15 15:53:59 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
