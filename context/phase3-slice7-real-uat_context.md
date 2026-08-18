# Task Context: phase3-slice7-real-uat

Created: 2026-08-18 08:45:00
Objective: 在清洁V2数据目录中从原始MG-K10-SAR III期与D001 II期方案完成首次解构、恢复、草稿审阅、发布和来源回跳的真实全流程验收，并定位任何偏差的共享根因
Task type: `long_horizon_code`
Risk: `high`
Selected agent route: `cms-smk` / `deepseek-v4-flash` / `max`

## Trigger Reason

This task was initialized through the Codex x Hermes complex-task entrypoint because it is expected to involve more than three execution steps, research/writing/report/code/report-visual work, or source-grounded verification.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-14-phase3-protocol-deconstruction/{prd.md,design.md,implement.md}`
- `.trellis/tasks/08-14-phase3-protocol-deconstruction/CHECKPOINT_20260818_SLICE6_COMPLETE_PAUSED.md`
- MG-K10-SAR V2.1 原方案（只读）：`/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/4. Protocol/MG-K10-SAR-001_临床研究方案_ V2.1_20250919_clean版 .docx`
- D001 V1.0 原方案（只读）：`/Users/smkzw/Documents/康哲项目资料/AI/入排/test-D001项目/CMS-D001 银屑病2、3期临床方案 v1.0-2025.12.21.docx`
- 旧解构结果只作反例和回归锚点，不得作为新项目的规则输入。

## Scope

- In scope: 从空 V2 数据根经真实 HTTP/API 完成上传、元信息确认、期别选择、持久任务、草稿审阅、发布、来源回跳、中断恢复和幂等/冲突反例。
- In scope: MG-K10-SAR III 期与 D001 II 期逐条临床语义抽核，包括官方父规则、子组件、ALL/ANY/NOT、例外、时间锚点、复合专业判断、审核节点和必做项来源。
- In scope: 只在共享合同、领域逻辑、持久任务或前端交互层修复可复现根因，不写入项目特异规则。
- Out of scope: 受试者资料、OCR、Patient Profile、实际入排判定、旧项目迁移、登录/多用户、安全测试。
- Out of scope: Slice 8 的三路视觉医学监查员试用；只有 Slice 7 所有确定性锚点通过后才启动。

## Success Criteria

- MG-K10-SAR III：方案编号 `MG-K10-SAR-001`、V2.1、2025-09-19，IN 7、EX 16、必做项 41；共享条款无“仅III期”噪声，“操作无缝”不会合并受试者空间。
- D001 II：方案身份与期别正确，IN 6、EX 30、必做项 50；与 III 期项目完全独立。
- 两套规则官方编号顺序、父子层级、来源闭包与按访视实例拆分的必做项目录逐项通过，不仅比较总数。
- 错传方案、错选期别、重复首次创建、摘录不匹配、占位必做项、取消、发布冲突和服务中断恢复均有可重现通过证据。
- 真实数据库、真实任务运行、真实浏览器和原始方案来源回跳通过；源 DOCX 的 SHA-256、大小、mtime 不变。
- 页面在 1920×1080、2560×1440、3840×2160 及 100%/150%/200% 缩放下无整页横向溢出、裁切、重叠、关键操作隐藏或宽度浪费。

## Risk Boundaries

- 仅写入本隔离工作树和其清洁临时 V2 数据根；不写回两份原方案、旧项目、原始受试者资料、人工 IE 表或旧报告。
- 不触碰主工作树中用户修改的两张 UAT recorder 截图。
- 不并行运行会重建同一 `frontend/dist` 的常规与真实 HTTP 套件。
- 不因调用空正文、规则数量偏差、来源断裂或期别污染而继续出可视报告；必须先查明共享根因。
- The delegated agent is not final authority; Codex owns verification and acceptance.

## Timeout Policy

- Do not mark the delegated agent failed for slow response alone.
- For complex or artifact-heavy work, wait and poll generously; use conference mode when multiple independent model perspectives are needed.
- Failure requires terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no progress after hard wait plus one retry.
- A provider catalog/auth/transport preflight is diagnostic, not a live capability verdict: timeout, auth refresh failure, malformed output, or a stale/incomplete catalog must be recorded and followed by one real route attempt. Explicit user-selected routes are not blocked merely because the catalog does not list them; only a missing executable or native transport boundary may stop before that attempt.

## Loop Log

- 2026-08-18 08:45:00: Task initialized by `tools/hermes_workflow_guard.py init-task`.
- 2026-08-18: MG-K10-SAR III 清洁真实运行完成：IN 7 / EX 16 / 必做项 41；唯一保留 EX-07 未命名 6 个月回溯锚点，未强行发布。
- 2026-08-18: D001 II 清洁真实运行完成并发布：项目代号 `D001-02`，IN 6 / EX 30 / 必做项 50；阻断 0，幂等重放通过。
- 2026-08-18: 从真实偏差修复共享根因：跨休眠租约续订、反馈防回退、门禁语义版本缓存、频次/数值分型、资料时效/事件窗分型、恢复 revision 生命周期及前端深层问题归属。
- 2026-08-18: 全量 V2 `765 passed, 2 subtests passed`；前端 `267 passed`；构建通过；真实 HTTP 三宽度 `3 passed`。
- 2026-08-18: 用户要求无损暂停。切片 7 完成，切片 8 三路独立医学监查员试用未启动。恢复依据为 `.trellis/tasks/08-14-phase3-protocol-deconstruction/CHECKPOINT_20260818_SLICE7_COMPLETE_PAUSED.md`。
