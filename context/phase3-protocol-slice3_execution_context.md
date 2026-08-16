# Execution Context: phase3-protocol-slice3

Created: 2026-08-14 16:58:40
Objective: 完成Phase 3切片3：冻结官方父规则和基线及以前必做项目录，建立受约束的方案解构Agent合同与确定性发布门禁，并用真实MG-K10-SAR III期及CMS-D001 II期逐项对账
Task type: `long_horizon_code`
Risk: `high`
Execution module trigger: Codex identified 4 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `opencode-go` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-14-phase3-protocol-deconstruction/{prd,design,implement,research}.md`
- MG-K10-SAR V2.1 和 CMS-D001 V1.0 原始 DOCX 只读方案；不修改或复制为更易通过的版本。
- 冻结官方父规则目录与基线前必做项目录是 Agent 输出完整性的确定性基准。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.

## Work Items

1. 实现章节索引和官方父规则目录冻结，保留官方编号、父子关系、期别与来源
2. 实现按期别和访视实例拆分的基线及以前必做项目录，重复访视不去重
3. 扩展方案解构Agent输入输出、提示词版本和最多两次同会话定向修复合同
4. 实现12类确定性发布检查、变异测试和真实方案目录对账

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Pause Checkpoint: 2026-08-14

- MG-K10-SAR III 期真实 Agent 运行已通过确定性门禁；证据目录为 `.trellis/tasks/08-14-phase3-protocol-deconstruction/metrics/real-agent-acceptance/mg-iii/`。
- 结果：IN 7、EX 16、41 个有效必做项，6 次同会话尝试，最终门禁问题 0，会话 `protocol-chat-57a31af30d0046b08e12e1432e309bd1`。
- D001 II 期真实 Agent 运行尚未启动。暂停恢复后先重跑整个方案测试集，再运行 D001；不进入切片 4。
- 当前分支含未提交的切片 3 实现。`frontend/e2e/screenshots/uat-recorder-desktop-overview.png` 和 `uat-recorder-e4-stop-banner.png` 是与本任务无关的并行改动，不得回退或纳入本切片提交。
