# Execution Context: phase5-slice60zn-authoritative-target-excerpts-20260828

Created: 2026-08-28 12:36:21
Objective: 修复全方案控制打包中权威官方规则与流程必做项只有身份、没有逐字来源摘录的问题，使直接上传DOCX/PDF后其他章节控制Agent能够读取跨章节完整逻辑；禁止D001特异硬编码，保持冻结目录哈希、来源一一对应和旧工件兼容。
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

1. 审阅FrozenCatalogItem、官方规则目录、流程必做目录及ProtocolControlPlanning链，提出最小合同迁移与失效关闭边界。
2. 在共享合同和两个目录构建器中实现可选逐字来源摘录，并由KnownOfficialRuleTarget/KnownRequiredProcedureTarget原样传给控制Agent；不得修改临床源文件。
3. 补充官方规则多来源、流程表多来源、旧目录兼容、长度/定位不一致拒绝及打包器传递回归，运行聚焦与协议层检查。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
