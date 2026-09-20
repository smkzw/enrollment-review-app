# Execution Context: phase5-slice61ci-package97-ae-followup-outcome-status-boundary

Created: 2026-08-30 10:39:19 CST
Objective: 建立并独立攻击验证 D001 II 当前 131 包计划第 97 包 body.p1138-p1149 的模型外来源闭包，保持不良事件处理、随访、资料收集和结果状态层次，不产生入排候选或调用临床模型。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `day`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `cursor/default -> google-antigravity/gemini-3.7-flash:high -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> opencode-go/muse-spark-1.2-contributor:xhigh -> openai-codex/gpt-5.6-luna:max`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `pi` / `cursor` / `default`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61ci-package97-ae-followup-outcome-status-boundary-execution-contract.md`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/coverage_manifest.json`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`
- Do not add production paths without explicit Codex authorization.

## Authorized Artifact Paths And Dependency Order

- Worker 01 may write the Package 97 config and parent checklist named in the execution contract.
- After Worker 01 completes, Worker 02 may write the Package 97 deterministic test module and dry-run prepare directory named in the contract.
- After Workers 01 and 02 complete, Worker 03 is read-only and may inspect all Package 97 artifacts.
- Codex will dispatch these workers sequentially; a later worker must not treat a not-yet-created prerequisite as a product defect.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 按合同创建第 97 包结构化配置与父级检查清单，严格核对 12 个自有来源、7 个只读附加来源及第 98/99 包边界。
2. 在配置完成后创建确定性变异测试并运行 dry-run prepare，覆盖禁用医疗措施退出路径、四类 OR 随访终点、相关事件尽力随访、分条件资料收集、六类结果状态和零候选。
3. 在配置、测试和准备产物完成后独立只读攻击审阅，寻找正反字段遮蔽、同义绕过、一般/相关事件随访压平、结果状态混同、相邻包吞并和候选越权。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
