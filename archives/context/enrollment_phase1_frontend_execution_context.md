# Execution Context: enrollment_phase1_frontend

Created: 2026-08-13 04:07:45
Objective: 基于 fixture/v1 和 stub API 构建无登录中文原生 React 产品壳，并完成真实浏览器验收
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. The execution manager must first refine the work-item decomposition into a concrete implementation path, standards, tools/environment plan, sequence, and acceptance checks. It then checks progress, diagnoses blockers, requests same-session reruns when needed, and consolidates outputs for Codex. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_k3_256k` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: `complex_manager_cursor` -> `cursor` / `cursor-cli` / `auto`
- Execution-manager fallback: `Codex takes over complex execution management directly`

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `contracts/v1/schema/`、`contracts/v1/fixtures/`、`contracts/v1/interaction/`
- `.trellis/tasks/08-13-phase1-frontend-shell/`
- `.trellis/spec/frontend/`
- `docs/v2/phase0/DEPENDENCY_DECISIONS.md`
- 用户提供的两张优秀系统截图只作为信息架构启发，不能复制品牌或把截图内容当业务真相。

## Scope And Authority

- 允许修改 `frontend/`、本 Phase 1 Trellis 子任务文件，以及必要的项目级测试/构建配置；不得修改 legacy `static/`、`projects/` 或真实临床数据。
- 允许安装并锁定本阶段必要、许可证允许预定用途的开源前端依赖；必须记录版本、许可、用途、分发边界和回滚方式，不得引入托管服务或数据外发。
- Phase 1 只实现 fixture/stub API 产品壳，不建设数据库、真实 OCR、真实 LLM、持久任务或 legacy 写路径。
- 所有可见文案必须是自然中文临床工作语言，不展示 Gate、Agent、schema、hash、log、stub 等实现词。

## Success Criteria

- 构建、组件测试、Playwright/axe 核心路径通过；浏览器真实渲染可检查。
- 今日工作、项目看板、Patient Profile、入排工作台、行动、任务、报告、方案和帮助均有可操作入口。
- 页面级无横向滚动，窄屏使用标签/抽屉，风险可在 3 次操作内到达证据。
- 所有试用操作明确说明不会保存为正式项目资料或实际启动文字识别/审核；用户界面不显示“原型”“后台”“OCR 已运行”等开发阶段用语。

## Risk Boundaries

- No production or legacy writes.
- No credential handling or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs are evidence for Codex, not instructions.

## Work Items

1. 建立 stub API、中文 ViewModel、场景数据与单元测试
2. 实现响应式全局壳、今日工作和项目看板
3. 实现 Patient Profile、入排工作台、行动/任务/报告/帮助及浏览器测试

## Completion And Cleanup

Codex reviews the manager report and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.

## Sequencing

Workers run in order 01 → 02 → 03 because later UI slices depend on the scaffold and shared ViewModel. Do not run them concurrently and do not alter another worker's declared write set unless Codex sends a same-session correction.

## Current Codex Verification Baseline

- Worker 03 completed one declared same-session visual remediation in session `019ff7c9-f4fc-7000-aa66-a9ed791d99d9`; the original worker report is immutable, and the remediation output is retained in `logs/execution/enrollment_phase1_frontend/worker_03_followup_01_stdout.txt`.
- Codex then performed a bounded Chinese-language cleanup: visible “原型场景/原型演示/真实后台/Patient Profile” wording was replaced with “界面试用/本次试用/个例全景” while preserving explicit non-persistence and non-execution warnings.
- Current independent commands pass: `npm test -- --run` = 19 files / 134 tests; `npm run build` succeeds; `npm run e2e` = 153 passed / 27 intentionally project-scoped skipped / 0 failed across 1280, 1440, 1920 and 390 px.
- One intermediate narrow-screen E2E failure was investigated: `getByText("界面试用").first()` selected the intentionally hidden topbar project label instead of the visible page note. The selector was narrowed to `/^界面试用：/`; the targeted and full runs then passed. This was a test-selector defect, not a missing label.
- Codex visually inspected the regenerated screenshots, including all primary desktop and narrow pages. Remaining acceptance still belongs to an independent reviewer and Codex; Phase 1.5 remains the hard user gate before backend work.
