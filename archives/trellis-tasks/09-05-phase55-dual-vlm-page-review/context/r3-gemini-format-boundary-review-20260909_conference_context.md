# Conference Context: r3-gemini-format-boundary-review-20260909

Created: 2026-09-09 01:16:55 CST
Objective: 只读独立工程复查：当前app/llm/gemini_transport.py、gemini_oauth.py、page_review_format_repair.py、page_review_harness.py及执行/回执/恢复消费者与相关tests。产品当前仅GLM low与Gemini3.7 high，原生OAuth直连而非个人harness。核验一次格式纠正同模型同图不删事实不改数值、严格失败边界、可取消、响应记录和版本闭包；Gemini原生SSE错误/截断/OAuth刷新与凭据不外泄、实际high后缀映射及预检。指出实质缺陷与最小修复，不写代码不读.env/个人配置/临床原件，不调用模型/网络，不递归派发。产品已有真实24页18通过，一次失败页重读22通过，剩两页格式错；这些数量不是临床验收。不要依赖执行者论述，以当前代码与测试为据。
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r3-gemini-format-boundary-review-20260909`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- TODO: Add authoritative local files, extracts, datasets, screenshots, URLs, or user-provided materials.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: TODO
- Out of scope: TODO

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

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

- 2026-09-09 01:16:55 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
