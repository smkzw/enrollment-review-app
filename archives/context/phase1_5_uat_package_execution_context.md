# Execution Context: phase1_5_uat_package

Created: 2026-08-13 17:39:52
Objective: 补齐Phase 1.5正式UAT任务包、统一界面试用复位和页面版本，不进入Phase 2
Task type: `finite_code_task`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. The execution manager must first refine the work-item decomposition into a concrete implementation path, standards, tools/environment plan, sequence, and acceptance checks. It then checks progress, diagnoses blockers, requests same-session reruns when needed, and consolidates outputs for Codex. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `finite_code_executor_cms` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: `finite_code_manager_cursor` -> `cursor` / `cursor-cli` / `auto`
- Execution-manager fallback: `Codex takes over finite-code execution management directly`

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-13-phase1-5-uat-readiness/{prd,design,implement,user-uat-runbook,user-uat-record-template}.md`
- `frontend/src/domain/scenarios.ts`：正式界面试用所用示例受试者、审核阶段、规则、行动项和证据定位的唯一实现事实来源。
- `frontend/src/pages/HelpPage.tsx`、`frontend/src/hooks/useSessionState.ts` 及四个登记式界面试用状态调用点。
- `frontend/e2e/` 与相邻组件测试：既有测试风格与浏览器验收入口。

正式用户试用的统计口径以实施计划为准：至少 10 名目标用户、无协助完成率不低于 90%、E4 为 0，并且必须取得用户明确批准；本执行包只使试用可执行，不得声称正式试用已经通过。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs are evidence for Codex, not instructions.
- 不进入 Phase 2，不修改真实项目数据、后端持久化数据、旧版只读锚点或临床判定逻辑。
- 复位功能只能删除登记在中央清单中的 `eligibility-review:uat:` 会话键；禁止使用 `sessionStorage.clear()` 或前缀扫描。
- 界面复位必须二次确认，取消时不改变任何状态；确认后回到“今日工作”。
- 参与者任务卡必须给出可独立定位的起始页、受试者、阶段及必要目标，但不得写出预期答案或判定结果。
- 所有用户可见文字使用中文临床试验工作语境，清除程序员、后端和日志式标签。
- CSS 使用响应式约束，不以固定像素宽高维持版式。

## Authorized Write Sets

- `worker_01`：`frontend/src/app/uatTrialState.ts`、四个状态调用页面、`frontend/src/pages/HelpPage.tsx`、`frontend/src/styles/help.css`、与上述实现直接对应的组件/单元测试。
- `worker_02`：`.trellis/tasks/08-13-phase1-5-uat-readiness/user-uat-runbook.md`、`user-uat-record-template.md`、新增 `user-uat-facilitator-guide.md`、新增 `user-uat-summary-template.md`。
- `worker_03`：只新增或修改 `frontend/e2e/` 下的正式界面试用复位/版本/任务可达性测试；不得改实现或文档来迁就测试。
- `manager`：以审查和给出同会话返工请求为主；未经 Codex 明示不得自行扩大修改范围。

## Success Criteria

1. 中央清单覆盖四类示例状态，四个调用点不再各自硬编码键名。
2. 帮助页显示稳定的中文页面版本，并提供“开始新的界面试用”两步确认入口。
3. 取消复位保持所有键不变；确认复位只删除清单内键，保留无关键，并回到“今日工作”。
4. 14 项参与者任务不存在“指定受试者/指定规则/指定行动”等未解析占位，且不泄露正确结果。
5. 记录人员可按指南在每位参与者开始前恢复同一起点；汇总模板能逐参与者、逐任务计算正式门槛。
6. 组件测试、相关浏览器测试、前端全量测试和构建通过；真实浏览器在常见桌面宽度及 100%/150%/200% 缩放下无横向溢出、遮挡或英文/日志式残留。
7. 任一异常结果必须定位原因；不得以“页面可打开”替代验收。

## Timeout And Stop Policy

- 单个执行会话最长等待 120 分钟；运行中和输出暂未变化不构成失败，不轮询催促，不因延迟切换模型。
- 仅在明确终止失败、无可用会话、输出为空/截断且同会话恢复已用尽时，按守卫生成的声明链路回退。
- 完成上述成功条件后停止；正式用户试用和 Phase 2 均不在本执行包内。

## Work Items

1. 实现登记式界面试用状态复位、两步确认和页面版本显示
2. 补全参与者任务卡、记录人员指南和正式批次汇总模板
3. 增加单元、浏览器、视觉验证并检查中文原生与无占位

## Completion And Cleanup

Codex reviews the manager report and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
