# Conference Context: enrollment_phase1_visual_acceptance

Created: 2026-08-13 06:22:44
Objective: 独立审查 Phase 1 入排审核前端壳的中文医学监查用户体验、信息架构、响应式、证据可达与视觉完成度，给出接受或阻断结论
Task type: `visual_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

    - Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route. The Codex subAgent Luna route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
    - Other complex tasks use a Codex-chaired panel with no sub-venue chair. Participant 1 is Pi/Alibaba `qwen3.8-max` (xhigh) during the Beijing 22:00-07:00 window. Outside that window its exact Qwen Max node is replaced by Pi/OpenCode Go `deepseek-v4-flash` (max); during the night window, every exact Pi/cms-smk `deepseek-v4-flash` node is replaced by the same Pi/OpenCode Go route. Its remaining fallbacks are Pi/cms-smk `deepseek-v4-flash` (max) and Pi/OpenCode Go `deepseek-v4-flash` (max), with effective-route deduplication. Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority. The explicit Luna native/CLI compatibility route remains available for execution roles that declare Codex subAgent.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-13-phase1-frontend-shell/prd.md`
- `.trellis/tasks/08-13-phase1-frontend-shell/design.md`
- `frontend/src/`、`frontend/e2e/` 与 `frontend/e2e/screenshots/`
- 本地只读试用地址 `http://127.0.0.1:4173/`（由 Codex 启动，若不可达则以源码、测试和截图为准并明确记录）
- 本轮不得读取 legacy 临床项目、方案原文或受试者原始资料；这些不属于 Phase 1 视觉壳验收来源。

## Scope

- In scope: 面向不熟悉电脑和 AI 的中文资深医学监查人员，独立检查今日工作、项目看板、方案解构、受试者个例全景、入排工作台、行动中心、报告导出、任务与系统、系统帮助的导航、信息层级、中文表达、证据可达、响应式和状态表达。
- In scope: 检查 1280/1440/1920 桌面、390 窄屏及工作台 150%/200% 缩放截图；必要时在本地地址真实操作。
- In scope: 判断是否存在阻断 Phase 1.5 用户试用的问题，并把缺陷按“阻断/重要但不阻断/后续阶段”分级，给出可执行修复建议。
- Out of scope: 修改任何文件；实施后端、数据库、真实 OCR/LLM；临床结论正确性；安全性、权限或渗透测试；读取工作区外的临床资料；替用户决定“今日工作”或“项目看板”谁是默认首页。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- 明确给出 `接受进入 Phase 1.5` 或 `阻断并修订` 的结论，且每项阻断结论都有可复现页面、视口和证据。
- 检查可见界面没有 Gate、schema、hash、Agent、log、backend 等实现语言，也不把试用界面写成已真实完成 OCR、审核或持久化。
- 检查父子规则层级、状态文字与图标、定位精度、行动责任方和风险到证据不超过 3 次操作等核心合同。
- 不使用 Qwen 3.8；本轮固定走视觉会商的 Kimi K3 主路由，只有该路由发生可验证终态失败时才由 runner 按既定视觉链处理。

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; only a missing CLI or an explicitly invalid, retired, or unlisted model may block before live dispatch. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-08-13 06:22:44: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-13 06:27-06:48: Kimi K3 首轮只读视觉审查完成；发现时间窗字段契约错配这一阻断项，并列出七项重要问题。
- 2026-08-13 06:48-06:57: Codex 按 Wire 到 ViewModel 到界面的共享根因完成修订，137 项测试、构建和 153 项浏览器测试通过，并重生成截图。
- 2026-08-13 06:58-07:17: 原会话完成同会话复核，明确“接受进入 Phase 1.5”；未触发 fallback。
- 2026-08-13 07:17-07:23: Codex 关闭复核发现的非阻断残余：方案差异编号统一中文化；路由就绪等待修复视觉测试假阳性；缩放测试改为真实等效布局视口。全量验证再次通过。
