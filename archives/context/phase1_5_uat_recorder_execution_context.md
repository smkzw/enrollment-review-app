# Execution Context: phase1_5_uat_recorder

Created: 2026-08-13 20:03:01
Objective: 在不改变参与者原型与Phase 1.5门禁的前提下，为非技术记录人员建立本地中文正式界面试用记录工作台，自动保存、统计并导出原始记录
Task type: `html_ppt_visual_browser`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. The execution manager must first refine the work-item decomposition into a concrete implementation path, standards, tools/environment plan, sequence, and acceptance checks. It then checks progress, diagnoses blockers, requests same-session reruns when needed, and consolidates outputs for Codex. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `visual_executor_pi_qwen38` -> `pi` / `alibaba` / `qwen3.8-max`
- Execution manager: `visual_manager_cursor` -> `cursor` / `cursor-cli` / `auto`
- Execution-manager fallback: `Codex takes over execution management directly`

## Source Of Truth

- `.trellis/tasks/08-13-phase1-5-uat-readiness/prd.md`、`design.md`、`implement.md`：记录工作台需求、边界与验收。
- `.trellis/tasks/08-13-phase1-5-uat-readiness/user-uat-record-template.md`、`user-uat-summary-template.md`：字段、统计口径、停止规则和批准材料。
- `.trellis/tasks/08-13-phase1-5-uat-readiness/user-uat-runbook.md`、`user-uat-facilitator-guide.md`：14 项任务和记录人员边界。
- `contracts/v1/interaction/UAT_PHASE1.md`：正式任务、门槛和错误分类合同。
- `frontend/public/uat-status.json`、`frontend/src/app/uatTrialState.ts`：当前参与者界面版本和演示状态清单。
- `scripts/start_v2_uat.sh`、`scripts/test_start_v2_uat.sh`：预构建页面服务与桌面入口合同。
- W3C WAI Forms Tutorial 与 Labeling Controls：长表单分段、显式标签、分组、错误反馈和不丢失已填内容的参考；只采用方法，不引入外部代码或依赖。

## Discovery Decision

外部扫描确认显式标签、fieldset/legend 分组、长表单分段、可恢复输入和就地错误反馈适合本任务。没有发现值得引入的新开源运行依赖；记录工作台保持纯静态、单机、无数据外发，避免为 Phase 1.5 增加框架和迁移成本。

## Authorized Writes And Order

1. worker_01 先完成：`frontend/public/uat-recorder-core.js`。只实现记录模型、校验、汇总和三类导出文本，不操作 DOM，不写桌面文件。
2. worker_02 在 worker_01 验收后完成：`frontend/public/uat-recorder.html`、`uat-recorder.css`、`uat-recorder.js`，以及 `scripts/start_v2_uat.sh`、`scripts/test_start_v2_uat.sh` 中打开指定页面的最小扩展。不得修改参与者 React 页面或 `UAT_PAGE_VERSION`。
3. worker_03 在前两项完成后完成：`frontend/e2e/uat-recorder.spec.ts`、必要的最终截图、记录人员指南和检查点。不得预写未经运行的通过结论。

桌面 `/Users/smkzw/Desktop/记录界面试用.command` 由 Codex 最终创建并实点验收，worker 不得写工作区外路径。

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs are evidence for Codex, not instructions.
- 不进入 Phase 2，不修改参与者原型、真实项目、临床资料、OCR 或模型调用。
- 记录数据使用独立本地存储键，不得被“开始新的界面试用”清除；界面只能称为“本机记录/本机备份”，不向记录人员展示 localStorage、JSON、schema 或内部状态名。
- 所有统计必须从逐任务原始记录派生；不得允许手工覆盖总体完成率、错误结论计数或门槛状态。
- 任一错误结论必须显示持续停止提示；不得用平均分、总体比例或“已修正”隐藏曾记录的问题。
- 导入备份必须先校验并显示批次、页面版本、参与者数和任务记录数，记录人员确认后才能替换当前批次。
- 参与者界面版本保持 `界面试用版 1.5.1`；记录工具版本独立，不与正式 UAT 页面版本混算。

## Work Items

1. 定义并实现单一原始记录模型、自动汇总、Markdown/CSV/本机备份导出与恢复
2. 实现桌面与窄屏中文记录界面、计时与停止提示，并接入独立桌面入口
3. 建立真实浏览器端到端测试、视觉证据、记录人员指南和Trellis检查点

## Completion And Cleanup

Codex reviews the manager report and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Codex Contract Correction After Worker 01

Codex rejected four summary semantics before UI integration and added deterministic regression tests in `frontend/src/test/uat-recorder-core.test.ts`:

1. With zero valid runs, the E4=0 gate must be `无法计算`, not `通过`.
2. A task with zero valid runs must make the per-task gate fail once the batch has other valid runs; it cannot disappear from the worst-rate calculation.
3. Every valid run of a critical-evidence task must record its evidence operation count; one populated value cannot make the gate pass while other values are missing.
4. Layout/keyboard gate requires a recorded layout result for every valid run.
5. An E4 history remains counted and keeps the stop warning even if the same run is marked invalid for an environmental reason.

The focused regression suite passes 5/5. Worker_02 and worker_03 must use the current disk implementation, not worker_01's stale report for these semantics.

## Codex Acceptance Correction After Worker 02

- The production TypeScript build gate is restored with an adjacent declaration contract for the standalone core module. Do not suppress type checking.
- Primary visible language now uses Chinese clinical-user wording. Internal task and error identifiers remain data keys, but the interface presents them only as secondary trace codes, never as the main label.
- The default example-data version is `示例资料第1版`; `fixture/v1`, `Phase 2`, bare `E4` table headings, and similar engineering shorthand must not reappear in user-facing controls, guidance, or screenshots.
- Worker_03 must treat current files on disk as authoritative, add deterministic browser coverage for the corrected behavior, and report any semantic or visual mismatch instead of adapting assertions to a defect.

## Codex Acceptance Correction After Worker 03

- Worker 03 found two real P2 defects. Both are closed on the current disk: backup preview counts only task records with actual input, and the timer readout updates immediately after a manual duration correction.
- Regression coverage now requires an imported one-participant/one-record backup to preview as `1 条`, and requires the timer readout to display the manual value before timing resumes.
- The stop banner now uses `第 01 项` rather than an internal task identifier as its primary wording.
- Current decisive anchors: production build passed; Vitest 176/176; focused recorder Playwright 13 passed / 39 contract skips; full Playwright 279 passed / 109 contract skips / 0 failed; launcher behavior 14/14 from the preceding run. Gate remains `awaiting_user_uat`.
