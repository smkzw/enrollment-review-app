# Execution Context: r05-semantic-ordering-20260915

Created: 2026-09-15 13:03:04 CST
Objective: Implement source-bound semantic observation ordering using existing deterministic selector; no tests or runtime clinical adoption
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

- Read app/services/ordered_observation_selection.py, app/services/qualified_binding_selection.py (particularly _select_with_ordering and semantic branches), app/domain/contracts/observation_selection.py, app/domain/proposition_observations.py, app/services/predicate_proposition_calculation.py, app/projections/control_calculation_experiment.py. Read adjacent types only as needed.
- Design: docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 17.2. Latest user: construction only, no staged test files or test executions, product models/DB/browser must not start.
- WRITE SCOPE ONLY: new app/services/semantic_observation_selection.py. Do not edit integrations, existing selector/contracts, docs, tests, configuration or clinical sources. Return report via runner. Owner handles integration/versioning.
- Implement a reusable typed helper for selecting existing verified semantic relation rows when policy.selection is declared. Inputs may follow existing caller objects but expose a clear API; output fact IDs, content+date pair IDs, reasons, ordering audit and retained relations without mutating input. Delegate date selection to select_ordered_observation, never duplicate it. Verify every source content pair (value/assertion_basis) is represented by verified relations before choosing, use all supplied-fact accounting, require qualified date_range for every candidate even without a time constraint, require review conflict context, pass event/source validity time purpose and frozen anchors. Accept only explicit single/latest-or-earliest policies supported by selector. Preserve scope_candidates_complete as supplied-input coverage only, never infer clinical completeness. Excluded relations are separately preserved as not-selected, not invalid. Return unresolved and no selected IDs/relations if any validation fails. Determine exact types from current sources. No regex clinical parsing, model/provider/project names, default favorable values, fabricated dates or clinical permission.
- Accept checks: read complete new definition and adjacent input contracts, compile only (py_compile); do not instantiate product objects or run tests. Report limitations including clinical completeness and source scope. Do not modify any other file even if related defects are found; report them for owner.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Add bounded reusable semantic ordering helper; preserve supplied-fact accounting and source relations, never infer clinical completeness; source/compile checks only

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
