# Execution Context: phase5-slice58i-d001-matrix-source-closure-20260826

Created: 2026-08-26 03:49:02
Objective: 在不修改D001源方案的前提下，将D001 II其他章节控制矩阵的临时来源身份绑定到当前冻结全文清单，完成期别、关系、重复与严格来源闭包验证，并保留人工临床验收边界。
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `codex-subagent` / `codex` / `gpt-5.6-luna`
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

1. 只读审计当前25条其他章节控制、82行合并矩阵和冻结coverage manifest，给出临时su-cross来源到真实结构单元的确定性映射、重复/期别/关系风险及不能自动闭包的项目，不修改文件。
2. 基于审计结果实现最小通用映射与闭包路径，更新生成器或矩阵工件，禁止按source_ref模糊择优、禁止项目特异规则进入共享代码，并补充聚焦回归。
3. 独立运行严格来源、期别、时间、节点、逻辑、例外、重复关系验证，复核D001方案哈希和矩阵claims_complete边界，报告未闭合项并拒绝虚假完成。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
