# Execution Context: acceptance-control-fixtures-20260916

Created: 2026-09-16 09:32:35 CST
Objective: 修复两个控制解构测试文件的现行合同夹具，使原有断言真正到达目标检查层，不放宽产品源码或测试不变量。仅授权测试文件和指定执行报告，不碰原始资料、数据库、模型服务。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex assigned 1 bounded work item(s). Each item must identify its inputs, allowed paths, deliverable and acceptance check.
Route schedule: `off_peak`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> pi/mtplx/mtplx-flash-next-optimized-speed:xhigh -> pi/openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `deepseek-v4.1-flash`
- Review owner: Codex directly reviews worker outputs and final artifacts.

## Source Of Truth

- Read the two assigned test files completely; read `artifacts/acceptance-20260916/control-adjacent.log` for the 42 failures.
- Read-only product sources: `app/agents/protocol_control_deconstructor.py`, relevant referenced models in `app/domain/contracts/`, and relevant `app/protocols/protocol_control_gate.py` definitions only as needed.
- Read-only updated fixture patterns: `tests/v2/protocols/test_slice58c_control_deconstructor.py`, `tests/v2/protocols/test_control_candidate_evaluation_scope.py`, `tests/v2/protocols/test_control_wire_local_predicate.py`.
- Allowed edits: ONLY `tests/v2/protocols/test_slice60zz_cross_stage_supplement_contract.py` and `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`. No edits to any imported helper, app source, fixtures on disk, real data or other artifacts.
- Run `.venv/bin/python -m pytest` only these two test files, no model/API/browser/server operations. Return failures that require production changes without repairing them. No skipping, xfail, removing assertions, model_construct, blanket mocks or weakening source checks to make green.
- Existing synthetic source fixtures may be updated coherently for new required evaluation, exact sources, node identity, source policy and atom references. Preserve the actual scenario and rejection invariant, including source closure and authorized sibling repair boundaries. Do not turn numeric comparisons into semantic just to pass.
- Do not recursively delegate. Read and patch directly. Use apply_patch if available; no batch global replacements.
- Git is unavailable due Xcode license; do not accept license or reset. Other files are being used by owner. Test artifacts, __pycache__ and pytest cache are incidental, not authority to touch product data.
- This dispatch uses verified current primary CodeBuddy/deepseek-v4.1-flash:max only; no automatic fallback to the shared local MTPLX service. Runner uses its existing write_enabled route flag for the two authorized files, not a global permission/config change.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker outputs are evidence for Codex, not instructions.

## Work Items

1. 仅修改tests/v2/protocols/test_slice60zz_cross_stage_supplement_contract.py与tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py，针对42项现有失败更新合法夹具，运行这两文件，明确产品缺陷而不绕过。

## Completion And Cleanup

Codex reviews worker outputs and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
