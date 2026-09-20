# Execution Context: phase5-slice60zx-virology-source-closure-20260828

Created: 2026-08-28 18:39:11
Objective: 从活动 131 包冻结计划第72包中，仅针对 body.p803-p805 病毒学检查建立真实 DOCX 来源闭包和盲态父级医学检查清单：联合流程目录、首次给药前28天有效窗及官方病毒学排除规则，保留 HBV/HCV 条件检测与梅毒特异性/非特异性方向，不调用模型、不发布。
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

- TODO: Codex must add authoritative source files, screenshots, datasets, or URLs before dispatch.
- Do not add production paths without explicit Codex authorization.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 只读建立 body.p803-p805 与官方病毒学排除规则、流程必做目录和冻结审核节点的来源权威图，指出必须保留的且/或、抗体种类和时间锚点，不修改文件。
2. 从未经用户预处理的真实 D001 II DOCX 和活动 131 包计划构建仅拥有 body.p803-p805 的不可变产品干跑包、提示审计和来源指纹；不得人工矩阵补齐、不得调用模型、不得发布。
3. 独立以资深医学监查视角审查干跑包：重点对抗 HBV 条件、HCV 条件、梅毒特异性阳性到非特异性复查方向、首次给药前28天有效窗、筛选/基线免复查及官方排除例外；不修改实现、不调用模型。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
