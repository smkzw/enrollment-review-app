# Conference Context: phase4-slice46-independent-uat-r3

Created: 2026-08-21 12:31:41
Objective: 在正式非试用构建上由指定三模型独立完成 Phase 4 清洁库端到端视觉试用，核查资料上传、识别核对、证据原件联动、版本生成启用、恢复和宽屏体验
Task type: `html_ppt_visual_browser`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair: Pi/Oh My Pi `kimi-code/k3-256k` (high). If unavailable, the runner tries Grok Build `grok-4.6` (high), then the distinct Cursor `cursor-grok-4.6-high` route, then the distinct Pi/OpenCode Go `gpt-5.6-luna` (max) route, then Codex subAgent Luna (max). The Codex subAgent route remains a separate native/CLI compatibility path.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/CMS-SMK `deepseek-v4-flash` (max) -> Pi/OpenCode Go `gpt-5.6-luna` (max) -> Kimi Code `k3-256k` (high). Participant 2 is Grok Build `grok-4.6` (high), with the distinct Cursor `cursor-grok-4.6-high` and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Source Of Truth

- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`
- `docs/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`
- `.trellis/tasks/08-19-phase4-evidence-ocr-v2/{prd.md,design.md,implement.md}`
- `prompts/conference/phase4-slice46-independent-uat-r3/common.md`
- 合成资料：`runs/conference/phase4-slice46-independent-uat-r2/source/synthetic_screening_record.pdf`
- 三个角色分别使用 4193/8921、4194/8922、4195/8923；每组数据库和处理目录互相隔离。
- 前端均来自普通 `npm run build`，`VITE_ENROLLMENT_INTERFACE_TRIAL` 未启用。

## Scope

- In scope: 从真实项目和受试者目录进入证据工作台，资料预览/取消/确认、OCR 与核对、原件联动、版本生成/启用/恢复、帮助和 1080P/2K/4K 宽屏视觉试用。
- In scope: 预期外结果须复现并追查到资料、页面、接口、处理状态、定位或语义层，不接受只看源码的结论。
- Out of scope: 登录、安全测试、Phase 5 临床事实/Patient Profile/逐条入排判断、真实临床资料、生产目录和应用源码修改。

## Success Criteria

- CodeBuddy CLI `hy3:max`、Pi `cms-router/minimax-m3`、Grok Build `grok-4.6:medium` 各自返回有截图和真实操作证据的独立报告；不静默替换模型。
- 每个角色使用自己的正式非试用页面、后端与清洁库，不得读取其他参与者输出或复用其浏览器状态。
- 从普通导航可到达唯一真实受试者；页面请求进入真实持久化和处理服务，不以前端试用夹具冒充。
- 三个角色至少完成上传到版本生成/启用或给出可复现的真实阻断，并覆盖恢复、帮助和三档宽屏视觉。
- 禁止通过 DOM 强制点击禁用按钮来模拟用户；可用开发工具取证，但必须区分普通用户可达行为。
- Codex 复核报告、数据库状态和关键原图；仅共同根因或独立可复现问题进入修复队列。

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

- 2026-08-21 12:31:41: Conference initialized by `hermes_workflow_guard.py init-conference`.
- 2026-08-21: R2 被判定为环境污染，不作验收；原因是试用版前端与真实后端混用。R3 改为三组普通构建和独立清洁库。
