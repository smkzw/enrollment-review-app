# Execution Context: phase5-slice60n-history-collection-contract-20260828

Created: 2026-08-28 08:26:40
Objective: 只读审查D001 II第67包的知情同意、人口学、既往/现病史和治疗史来源，形成下一代表组的项目无关结构化合同、父级临床验收清单与最小实现建议；不得修改文件、不得调用内置语义模型、不得把人工金标准注入Agent修订。
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `cursor` / `cursor-cli` / `auto`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- 当前活动冻结计划：`artifacts/phase5-slice59i-d001-phase-table-caption-rebaseline-20260827/frozen_phase_plan.json`
  - SHA-256：`f0aa7e4bccad782ad5472c1f446f079e26343f694ad3ddca401bfbef89f38250`
  - 计划 ID：`papl-40b1237a22e538a278b4fd5e`
  - 包数：`131`
  - 第 67 包唯一成员：`body.p764`、`body.p766`、`body.p767`、`body.p768`、`body.p769`、`body.p770`、`body.p771`、`body.p772`、`body.p773`
- 当前活动结构化来源：`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/structure/`
- 当前活动覆盖与阶段证据：`.trellis/tasks/08-22-phase5-clinical-facts-profile/research/d001-ii-phase-closure/`
- `phase5-slice58p`、`phase5-slice58q`、`phase5-slice58r6` 等 137/138 包计划，以及旧 `package67` 运行结果，只能用于历史差异追踪；不得用其包序号解释本任务的“第 67 包”。
- 若来源路径、哈希、计划 ID、包数或包成员任一项不一致，必须停止语义结论并报告身份冲突，不得自行选择其他快照继续。
- 不得读取或修改生产环境与原始临床资料；本任务只读上述工作区冻结证据。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 核对冻结第67包body.p768/p770/p772/p773及已知官方规则、流程节点和相邻来源，给出最小来源闭包、应处置/应新增语义及不应纳入的治疗后内容。
2. 从资深医学监查视角分析病史/治疗史收集范围：筛选与基线节点、近2年尽可能收集、排除标准各自回顾窗、银屑病完整病程、记录不完整与缺源文件的差异，形成父级逐项验收清单。
3. 审查现有控制合同、Agent提示和确定性门禁能否表达资料收集义务、时间范围与官方排除标准关系；识别把两年范围扩散、把筛选和基线压缩、把资料缺口误判为排除的系统风险及最小通用修复建议。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
