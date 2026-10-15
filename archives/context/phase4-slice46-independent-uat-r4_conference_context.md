# Conference Context: phase4-slice46-independent-uat-r4

Created: 2026-08-21 14:12:31
Objective: 以真实医学监查人员视角，在清洁隔离的正式本地系统中端到端验收 Phase 4 资料上传、处理、OCR核对、被提及资料、生成启用、原件滚动与重点标注、中文交互及宽屏视觉；测试者必须使用系统自身功能，不替代系统独立Agent作临床判断。
Task type: `visual_delivery_conference`
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

- 架构与边界：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`、`docs/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`、`.trellis/tasks/08-19-phase4-evidence-ocr-v2/`。
- 本轮产品实例：三个独立正式 V2 数据目录，各自仅播种 `contracts/v1/fixtures/subject-barrier.json`；页面上传文件仅使用 `runs/conference/phase4-slice46-independent-uat-r2/source/synthetic_screening_record.pdf`。
- 测试对象固定为 `subject-barrier` / `episode-barrier`，测试者只通过浏览器和正式 `/api/v2` 交互，不使用路由拦截伪造数据。
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: 首次完整资料快照、增量补充、文件处理、识别原文/校对文本、识别风险核对、被提及资料闭环、候选版本生成与启用、刷新恢复、原件连续滚动、真实定位和宽屏中文交互。
- In scope: 以懒惰但专业的资深医学监查员视角找出不可理解、不可恢复、证据不诚实、视觉层级混乱和操作负担过高的问题。
- Out of scope: 安全性测试、真实临床数据、最终入排决策、Phase 5 尚未交付的临床语义匹配。如当前页面没有可调用的临床独立 Agent，必须记录产品边界，不得由测试者自己代替 Agent 做判断。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- 每个测试者实际进入自己的清洁实例，执行不少于一条完整上传到启用路径，并以截图、页面文本、网络/任务结果作为锚点。
- 报告分开直接观察、推断和建议，按阻断/高/中/低排序，不用“流程能跑通”代替真实用户验收。

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

- 2026-08-21 14:12:31: Conference initialized by `hermes_workflow_guard.py init-conference`.
