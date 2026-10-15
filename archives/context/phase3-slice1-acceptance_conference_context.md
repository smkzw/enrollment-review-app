# Conference Context: phase3-slice1-acceptance

Created: 2026-08-14 13:36:25
Objective: 独立审查 Phase 3 第一切片的方案原文登记、DOCX结构提取、受控渲染、来源对齐、不可变存储和真实方案回归，寻找会导致临床规则错漏或虚假来源定位的系统性缺陷；仅审查，不修改文件。
Task type: `high_risk_contradiction_review`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

    - Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route. The Codex subAgent Luna route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
    - Other complex tasks use a Codex-chaired panel with no sub-venue chair. Participant 1 is Pi/Alibaba `qwen3.8-max` (xhigh) -> Pi/OpenCode Go `deepseek-v4-flash` (max) during the Beijing 22:00-07:00 window; daytime is Pi/CMS-SMK `deepseek-v4-flash` (max) -> Pi/OpenCode Go `deepseek-v4-flash` (max). Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority. The explicit Luna native/CLI compatibility route remains available for execution roles that declare Codex subAgent.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-14-phase3-protocol-deconstruction/{prd.md,design.md,implement.md,research.md}`
- 当前未提交的 Phase 3 第一切片代码与测试差异，包括 `app/protocols/`、`app/domain/contracts/protocol_ingestion.py`、`app/storage/migrations/versions/0004_protocol_ingestion.py`、`tests/v2/protocols/`。
- Codex 最终独立复跑结果：方案切片测试 47 项通过；全仓 514 项及 18 个子测试通过、1 项遗留 OCR 缓存夹具缺失而跳过；两份真实方案的结构提取、渲染、页文本和来源对齐回归通过，所有保留的精确范围均可在声明页回验且跨结构块碰撞为 0。
- 外部真实方案文件只由 Codex 在用户授权下作只读验收。会议参与者不得读取工作区外原始临床资料，须审查测试契约、实现和仓内证据。

## Scope

- In scope: 只读审查原始文件登记、DOCX OOXML 结构提取、LibreOffice/PDF 渲染、双通道来源对齐、领域契约、SQLite 迁移、不可变块集及测试充分性；指出可导致规则漏提、编号错位、来源伪精确或不可复现的系统性缺陷。
- Out of scope: 修改任何文件；审查工作区外受试者资料；Phase 3 后续的规则语义 Agent、发布门禁与前端；安全性测试；遗留系统重构。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- 不读取或修改工作区外原始临床资料；不修改任何代码；Codex 保留最终验收权。
- 每项问题必须给出文件/符号或测试证据、临床影响、可复现路径和建议修复；明确区分阻断、后续切片责任与非问题。

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

- 2026-08-14 13:36:25: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-14: 初审发现重复文本伪精确、源哈希分叉、可变渲染件和 OOXML 覆盖缺口；实现侧完成系统性修复并新增回归。
- 2026-08-14: 最终独立复核确认 MG-K10 与 D001 的精确范围碰撞均为 0、页面摘录回验失败均为 0；会议结论为返修后通过。
- 2026-08-14: 将诚实拒绝导致的页级召回不足列为后续限制；身份字段权威性与规则正文定位精度必须在切片 2 分级，受限插值只可作提示。
