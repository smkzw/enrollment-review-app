# Execution Context: phase5-slice60x-icf-demographics-source-closure-20260828

Created: 2026-08-28 09:37:59
Objective: 基于当前D001 II期131包冻结计划，为知情同意和人口学第103/104包建立稳定source_ref来源闭包、既有流程目录核对与独立父级临床验收清单；仅在通用合同确有缺口时提出最小实现，不运行受试者/OCR/浏览器，不把金标准注入Agent。
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

1. 独立核对body.p767/p768知情同意原文、流程表body.t5.r5、脚注body.p315和IN-01/IN-02之间的权威边界，输出是否已有流程目录完整覆盖及必须保留的时序/证据语义。
2. 独立核对body.p769/p770人口学原文、流程表body.t5.r6、脚注body.p317及IN-02年龄/性别规则，区分资料采集流程与入选判定，输出重复/补充关系和父级检查点。
3. 以共享架构审阅者身份检查当前代表组harness、required_procedure处置、精确访视和资料家族合同是否足以表达知情同意/人口学；只报告通用缺口、所需确定性门禁和最小回归，不写项目特异规则。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
