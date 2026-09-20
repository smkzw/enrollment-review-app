# Execution Context: r05-qualified-binding-consumer-20260914

Created: 2026-09-14 13:45:20 CST
Objective: Implement the missing bounded consumer from persisted dual qualification to explicit frozen-review selections, including all unresolved identities and approval boundary, without enabling adoption or using category aliases.
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

- Sources: docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md section 17.1.1; reviews/codex_conference_r05-formal-consumer-closure-20260914_review.md; current app/services/binding_qualification.py and binding_qualification_support.py; app/domain/contracts/binding_qualification.py; app/services/frozen_review_calculation.py, app/services/component_review.py, app/projections/control_calculation_experiment.py. Read complete affected definitions and actual callers.
- Allowed edits: a small consumer module under app/services and if needed its contract under app/domain/contracts; app/services/frozen_review_calculation.py; reuse/extract a completed qualification loader from existing binding_qualification.py if needed. No other edits without reporting need. Do NOT add an API, registration, new queue, mock clinical proof, auto-enabled setting or publisher. Do not modify source reports/DB/raw clinical documents or other dirty work. No recursive delegation, no external models or app startup/import, no tests or test edits. Use project .venv for py_compile only and apply_patch for manual edits. Do not write runner-owned report.
- Concrete completion: reconstruct completed qualification from frozen source, exact job summary checkpoint and stored two-lane request/response receipts, not trusting a caller-supplied summary hash alone; reuse existing verification instead of duplicating 500-line verifier. Expose source-bound usable/unresolved explicit per-component/per-atom selections with all expected identities accounted for. A completed qualification is NOT itself adoption authorization. Future owner authorization must bind qualification algorithm/input/model-route identities and approved evaluation evidence; absent authorization must reject formal use, never manufacture authorization. Do not remove LiteralFalse flags on existing historical qualification contracts.
- Do not treat dual_agreement of two rejected/unresolved judgments as usable. Check every required semantic dimension, structural errors/pending checks, provenance, current frozen context, attributes and observation-scope requirements. No numeric unit/date conversion by string guessing, no matching clinical entities/fact_type aliases. Semantic and investigator_judgment evidence must not be coerced into a deterministic value. Direct arithmetic can only use qualified operand fields; preserve unsupported modes/derivations and unknown temporal scope as explicit unresolved. Keep every candidate rejection with concrete reason, including no candidate identities, not merely all UNKNOWN with no usable path.
- Integrate into existing frozen calculation via a clearly source-verified input path, not by returning another accepted=false JSON without a consumer. Keep existing isolated explicit-selection call compatible, distinguish its non-authoritative nature. The new input cannot be forged by just supplying a boolean/dict from model output. Construction does not create any authorized runtime policy or turn on adoption; final isolated evaluation/user approval is still required. If a precise missing contract blocks safe implementation, report the concrete issue rather than silently narrowing scope.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. Build a complete receipt-verified selection consumer for existing binding_qualification outputs and integrate it at calculate_frozen_review entry as an explicit alternative input. Require an explicit version-bound adoption authorization supplied by owning service; no default enabling or environment auto-discovery. Preserve unresolved identities and reject unsupported semantic/derivation/coverage rather than turn agreement alone into fact truth.

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
