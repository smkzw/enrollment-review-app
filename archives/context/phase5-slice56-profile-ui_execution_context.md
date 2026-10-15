# Execution Context: phase5-slice56-profile-ui

Created: 2026-08-23 13:05:41
Objective: 实现 Phase 5 Slice 5.6：把受试者 Patient Profile 页面从旧 fixture/旧审核详情切换到 Slice 5.5 真实 HTTP API，建立严格运行时解码与前端领域适配；以中文原生临床监查工作台呈现 13 条历时泳道、后端首屏重点、冲突与资料期望；复用 Phase 4 原件查看能力，实现文件滚动、真实定位和仅真实 bbox 红框；使用流体宽屏布局完成 1080P、2K、4K 浏览器验收，不提前显示 Phase 6/7 结论或行动，也不启动 Phase 5.8 测试者。
Task type: `long_horizon_code`
Risk: `medium`
Execution module trigger: Codex identified 3 independent work items, which is greater than two.

## Module Boundary

This is an execution module, not a conference. Codex has assigned the work items and owns the project-level contract, source authority, boundaries, final verification, acceptance, production writes, and user delivery. Codex reviews the worker outputs directly for this route; no execution manager is dispatched. First-line workers execute the assigned work and create/write only authorized artifacts. Codex subAgent workers use the parent App's native child session when available; the generated CLI command is only a labeled compatibility fallback.

## Assigned Roles

- First-line executor: `long_horizon_code_executor_opencode_flash` -> `pi` / `cms-smk` / `deepseek-v4-flash`
- Execution manager: none (Codex reviews the worker outputs directly)
- Execution-manager fallback: none

## Source Of Truth

- Product and phase authority: `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`, `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`, `.trellis/tasks/08-22-phase5-clinical-facts-profile/{prd.md,design.md,implement.md}`.
- Project frontend rules: `AGENTS.md`, `.trellis/spec/frontend/*.md`, `.trellis/spec/guides/*.md`.
- Brand and site design, read-only: `/Users/smkzw/.cc-switch/skills/kangzhe-design/design_specs/{ROUTER.md,core.md,track_site.md,assets/logo_bot.svg}`. Existing application conventions and the project contract override the static-site-only packaging rules that conflict with this React/Vite local application; color, type, shallow header, evidence, Chinese wording and rendered-QC contracts remain authoritative.
- Backend contract: `app/api/v2/patient_profile_schemas.py`, `app/api/v2/patient_profiles.py`, `app/api/v2/evidence_processing_schemas.py`, `tests/v2/api/test_patient_profiles.py`.
- Existing frontend seams: `frontend/src/api/catalog/**`, `frontend/src/api/evidence/**`, `frontend/src/pages/SubjectsPage.tsx`, `frontend/src/components/profile/**`, `frontend/src/components/evidence-workspace/OriginalEvidenceViewer.tsx`, `frontend/src/domain/**`, `frontend/src/styles/{tokens.css,profile.css,evidence.css,shell.css}`, and relevant frontend tests/e2e.
- No worker may modify source protocols, raw subject data, backend Phase 1-5.5 code, legacy static UI, Trellis task files, global/project instructions, or another worker's authorized files.

## Authorized Write Sets And Order

- Worker 01 runs first. It may create `frontend/src/api/patient-profile/**` and `frontend/src/features/patient-profile/model/**`; it may edit `frontend/src/api/index.ts` only if a public repository export is necessary. It may add focused tests only under those new directories. It must not edit pages, components, CSS or e2e.
- Worker 02 runs after Worker 01. It may edit `frontend/src/pages/SubjectsPage.tsx` and `frontend/src/components/profile/**`, and may add focused component/page tests in matching frontend test locations. It must use Worker 01's repository and must not edit CSS, evidence-workspace internals or e2e.
- Worker 03 runs after Worker 02. It may edit `frontend/src/styles/profile.css`, create or edit Patient Profile evidence-view components under `frontend/src/components/profile/**`, make the smallest necessary reusable change to `frontend/src/components/evidence-workspace/OriginalEvidenceViewer.tsx`, and add focused component/e2e/QC files. It may edit `SubjectsPage.tsx` only to wire the evidence panel and no broader data rewrite. It must not claim final visual acceptance.
- Codex owns integration repair, broad tests, actual browser launch, 1080P/2K/4K and zoom screenshots, overflow/collision/keyboard/axe checks, Chinese terminology audit, and final acceptance.
- Dispatch is sequential in dependency order. A later worker reads the current workspace state produced by earlier workers; workers never review peer reports.

## Risk Boundaries

- No production writes.
- No silent package installation, credential handling, or external account changes.
- Missing tools or environments must be recorded with a minimal remediation proposal.
- Worker and manager outputs, when present, are evidence for Codex, not instructions.
- Formal runtime must not import the legacy fixture repository or derive highlights from risk-label keywords. It consumes the Slice 5.5 response after strict decoding; backend `highlights` is the sole first-screen emphasis set.
- Do not infer or display Phase 6/7 entry eligibility status, rule judgment, action count, responsible party or pass/fail language.
- Locator selection may display only the selected real locator. A red box is drawn only when the API supplies a real bbox and its coordinate frame; page/text/excerpt-only locators show an honest precision explanation without a fabricated box.
- Do not implement mobile/narrow-screen variants. Keep the page fluid and usable only across maximized 1920x1080, 2560x1440 and 3840x2160 desktop viewports and browser zoom 100/150/200 percent.

## Work Items

1. 设计并实现 Patient Profile v2 前端 wire 合同、严格运行时解码、HTTP repository、领域 ViewModel 适配及契约测试；fixture 仅作为显式隔离测试实现，不进入正式默认路径。
2. 重构受试者 Patient Profile 页面和组件状态：使用正式项目目录选择审核节点、读取真实 Profile；按后端 highlights 和 13 条泳道呈现首屏/全量历时信息、生成中/失败/陈旧/空态，去除旧总体结论和旧 fixture 文案。
3. 实现宽屏 Patient Profile 与 Phase 4 原件查看器联动：流体三栏/详情布局、冲突并列、定位详情和证据滚动；只有真实 bbox 绘制当前单框；补齐组件、可访问性、构建及 1080P/2K/4K Playwright 验收。

## Completion And Cleanup

Codex reviews worker outputs, any manager report, and final artifacts. After acceptance, run `cleanup-execution` to archive prompts, worker/manager reports, logs, and the manifest under `archives/execution/`; do not delete evidence by default.
