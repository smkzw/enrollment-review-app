# Execution Context: phase5-slice61bw-package85-hepatic-injury-sae-boundary

Created: 2026-08-30 04:48:28 CST
Objective: 为D001 II冻结计划第85包body.p1055-p1066建立模型外来源闭包、临床反例门禁和可恢复验收证据，不调用临床语义模型或发布控制点。
Task type: `finite_code_task`
Risk: `low`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.
Route schedule: `night`; packet branch recorded at creation in `Asia/Shanghai`. Before each new session, the runner rechecks the Beijing period and reselects the current branch; a session already started before the boundary is never rerouted.
Effective worker chain: `codebuddy-cli/glm-5.3-flash:max -> codebuddy-cli/deepseek-v4-flash:max -> mtplx/mtplx-qwen38-27b-optimized-quality:medium -> openai-codex/gpt-5.6-luna:xhigh`

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor` -> `codebuddy` / `codebuddy-cli` / `glm-5.3-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/slice61bw-package85-hepatic-injury-sae-execution-contract.md`
- `AGENTS.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/prd.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/design.md`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`
- `artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/coverage_manifest.json`
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/structure/blobs/protocol_blocks/3946ea2c9780d0399b60245eafc4ab85087328a5da158b9d0938f8858302343d.json`
- Package 83/84 已验收配置、测试、父级清单和检查点只作实现模式与相邻所有权参考。
- 原始方案及冻结来源只读；不得修改生产路径或临床原始材料。

## Write Boundary

- `worker_01`、`worker_03`：只读核对与挑战，只返回 runner 管理的报告，不写项目工件。
- `worker_02` 仅可创建或修改执行合同中列出的 Package 85 配置、专项测试、父级清单和 runner 生成准备目录。
- 不得修改共享 runner、正式控制矩阵、协议解析实现、受试者、OCR、Patient Profile、前端或既有 Package 工件。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 独立核对原始DOCX、结构块、覆盖清单、冻结计划以及第84-86包所有权、列表层级、阈值和连接词。
2. 建立第85包配置、模型外准备、父级清单和专项回归，保持零入排候选并完整保留严重肝损伤与SAE记录报告逻辑。
3. 从AND/OR反转、基线正常与异常人群混同、阈值指标错配、以较小者为准丢失、诊断优先级与24小时弱化、跨包吞并角度进行独立反例挑战。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
