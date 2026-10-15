# Execution Context: r05-retest-capture-20260915

Created: 2026-09-15 14:56:31 CST
Objective: 实现方案条件复查的通用来源合同、双族解构与发布保护，不启用自动病例采信
Task type: `E03`
Risk: `high`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `pi/cursor/default -> codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- Read docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section17.2, plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md T3; read complete affected definitions and adjacent callers. Project AGENTS and .trellis/spec/backend/quality-guidelines.md apply. Do not read long historical reports or other agent outputs.
- Do not add production paths without explicit Codex authorization.

## Concrete Owner Contract

Implement only the source-capture increment, not patient relation/adoption. Current latest/earliest is NOT a retest policy. Add optional source-backed RepeatScheme to official AtomicPredicate and control ControlAtomEvaluationSpec, omitted when absent for historical serialization. Prefer small independent module; avoid circular imports. If reuse of TimeConstraint requires class placement in rules.py, keep that addition minimal instead of a new time algebra. Controls must reject a duplicated scheme inside their nested predicate. Both provider schemas, prompts, hydration and publication source gates must carry and validate it, with versioned new producer identities. Ordinary rules without retest stay compatible; unsupported retest wording stays explicitly unresolved, never silently latest/any/all.

Required meaning: permission optional/required/unresolved; original trigger with references to already represented condition where needed (do not invent fixed disease/lab/drug trigger dictionary); source-backed count limit with absence distinguished from an explicit unrestricted allowance; interval only with its explicit anchor (initial vs preceding repeat vs another named anchor, unknown stays unknown); replacement vs combination original policy. Existing ObservationPolicy decides aggregation AFTER authorized governing set exists, not the relationship. Do not assume last repeat is preferred, that same draw duplicates can be discarded, or that extras beyond count can be ignored. Do not embed an entire second predicate algebra; a trigger requiring numeric/PJ calculation must reference an existing condition, not let an LLM evaluate arithmetic. Preserve source span IDs/excerpts and every unresolved limitation. Source containment is necessary, not clinical proof.

This first increment must fail closed if a repeat scheme reaches current evaluators without the future verified relation consumer. Add shared reason repeat_relation_unverified => OBSERVATION_UNVERIFIED, no fabricated missing-record conclusion. Keep result evidence, no automatic adoption, no unverified claim of feature completion. Do not add a Boolean public bypass like verified=True. Owner will implement tuple-local relation proof and audited governing selection next.

Allowed writes ONLY: app/domain/contracts/repeat_scheme.py (if useful), app/domain/contracts/rules.py, app/domain/contracts/control_evaluation_spec.py, app/agents/protocol_deconstructor.py, app/agents/protocol_control_deconstructor.py, app/protocols/deconstruction_gate.py, app/protocols/protocol_control_gate.py (verify actual path before editing), app/domain/expression.py, app/domain/gates/assessment.py, app/services/control_operand_calculation.py. If an essential producer version lives in another existing file, report exact needed edit to owner; do not broaden writes. No docs/plans/test edits. No commit/reset/clean/install. No raw clinical files or databases. Preserve all existing dirty modifications.

Allowed checks: source reads, rg/skim discovery, git diff --check, Python compile via compile(source, filename, 'exec') without imports or pycache. No pytest or runtime checks. Report exact changed paths, versions, containment/compatibility trace and unresolved integration; do not create process documents.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 限定源码：复查来源合同、官方和跨章解构字段、来源校验、旧身份保留及未消费保护；不建测试，不运行产品

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
