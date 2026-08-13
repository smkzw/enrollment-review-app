# Conference Context: phase1_5_agent_monitor_retest

Created: 2026-08-14 01:31:30
Objective: 以资深中文临床试验医学监查员身份，在真实浏览器独立复验Phase 1.5修复后的入排审核工作台，深度检查风险分类、冲突证据、规则父子逻辑、Patient Profile、证据回源、中文交互、桌面与窄屏视觉，追查任何预期外结果并给出是否可进入Phase 2的独立意见
Task type: `visual_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

    - Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route. The Codex subAgent Luna route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
    - Other complex tasks use a Codex-chaired panel with no sub-venue chair. Participant 1 is Pi/Alibaba `qwen3.8-max` (xhigh) during the Beijing 22:00-07:00 window, with first backup Pi/OpenCode Go `deepseek-v4-pro` (max) and the original Flash fallback retained after it; during the night window, its CMS-SMK Flash fallback is rewritten to Pi/OpenCode Go `deepseek-v4-flash` (max). Outside that window, participant 1 uses the specific daytime chain Pi/CMS-SMK `deepseek-v4-flash` (max) -> Pi/OpenCode Go `deepseek-v4-pro` (max) -> Pi/OpenCode Go `deepseek-v4-flash` (max). Other exact Qwen Max nodes use the global daytime replacement Pi/OpenCode Go `deepseek-v4-pro` (max). Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority. The explicit Luna native/CLI compatibility route remains available for execution roles that declare Codex subAgent.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`：产品、临床语义和多 Agent 总体设计。
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`：分阶段实施边界；本轮只验收 Phase 1.5 修复，不把 Phase 2 尚未实现的能力误判为回归。
- `.trellis/tasks/08-13-phase1-5-agent-monitor-uat/prd.md`、`design.md`、`findings.md`：本轮验收合同和已识别问题分类。
- `frontend/public/uat-status.json`：当前可见版本必须为“界面试用版 1.5.2”。
- `frontend/e2e/screenshots/` 与 `frontend/e2e/screenshots/real-browser-zoom/`：自动截图和真实 Chrome 缩放证据，仅作导航线索，不能替代实际操作。
- 真实运行入口：`http://127.0.0.1:4173/`。可使用试用数据自由筛选、切换、批量选择、进入规则/证据/个例页面；不得修改源码或查看其他评审者输出。

## Scope

- In scope: 无登录直达、今日工作、项目看板、方案工作台、受试者与资料、入排工作台、行动中心、任务与系统、帮助；冲突来源并列、父子规则组合关系、例外条件、证据定位诚实性、节点期望覆盖、Patient Profile 风险优先、桌面/390px/真实缩放可用性、中文临床语境。
- In scope: 以懒惰但专业的资深医学监查员角色自由探索，不按开发者预设路径机械点选；出现空数据、结论冲突、导航错位或标签难懂时必须追到数据映射、状态语义或交互结构层的原因。
- Out of scope: 源码编辑、安全测试、真实受试者资料、正式医学结论、尚未进入 Phase 2 的真实方案解析/OCR/Agent 编排实现。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- 至少完成一条“风险概览 -> 规则子项 -> 冲突或相关证据 -> 返回个例”的往返，并检查另一受试者或另一阶段，避免只看单一示例。
- 明确区分已验证事实、主观体验、Phase 2 未实现项与真实阻断缺陷；给出“可进入 Phase 2 / 需先修复”的独立意见和最小理由。

## Parallel Work Rule

For logic-heavy, rigor-sensitive, or artifact-heavy tasks, each participant independently runs the whole bounded workflow and writes a separate output. Leads compare after all available participant outputs are in or explicitly marked pending.

## Timeout Policy

- Participant soft wait: 60 minutes.
- Large-task participant wait: 120 minutes.
- Chair hard wait: 120 minutes.
- Failure rule: Do not fail a model for slow response alone; fail only on terminal error, provider exhaustion/rate limit after controlled retry, empty/truncated retry output, or no useful progress after the high-budget same-session recovery loop. A catalog/auth/transport health preflight timeout or malformed response is diagnostic and must still allow one live route attempt; explicit user routes also proceed when the catalog is stale or incomplete, while a genuinely missing CLI or native transport boundary may block. If a resumable session exists after a step/size boundary, continue it before fallback; repeated identical output/tool evidence triggers the no-progress breaker.
- Pass/turn boundary: one conference prompt is one conference pass. The
  `--max-turns` value controls internal Agent tool-calling turns and is never
  set to 1 for substantive conference execution; generated participant and
  chair commands use the route budgets recorded by the guard.

## Risk Boundaries

- External Agents are advisory; Codex remains final authority.
- Codex owns visual/browser/PPT/PDF/rendered checks, live authority checks, final clinical/regulatory conclusions, and production writes.
- Do not mark a slow model failed solely due to latency.

## Loop Log

- 2026-08-14 01:31:30: Conference initialized by `hermes_workflow_guard.py init-conference`.
