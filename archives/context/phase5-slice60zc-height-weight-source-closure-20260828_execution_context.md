# Execution Context: phase5-slice60zc-height-weight-source-closure-20260828

Created: 2026-08-28 10:17:08
Objective: 基于活动D001Ⅱ期131包冻结计划，以未经用户预处理的原始DOCX结构化来源，独立核对第68包身高/体重测量章节与冻结流程目录的来源闭包，判断测量前准备、测量方法、设备条件、单位及记录精度是否形成独立入排审核控制增量；只读分析，不运行受试者、OCR、浏览器，不作最终临床接受。
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

1. 独立核对body.p774-p780身高测量来源，区分流程目录已覆盖的筛选期身高测量与章节新增的准备、体位、设备、呼吸和记录精度要求，给出source_ref级父级验收清单。
2. 独立核对body.p781-p783体重测量来源，区分流程目录已覆盖的筛选期体重测量与章节新增的校准设备、排空膀胱、着装、脱鞋、单位及小数精度要求，给出source_ref级父级验收清单。
3. 只读审阅当前ProtocolReviewControl、required_procedure、动作覆盖、义务原子和代表组harness，判断是否能通用表达测量方法/准备/记录精度，列出必须用确定性门禁阻断的语义压缩与最小非项目特异修复。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
