# Conference Context: phase5-slice58-cross-section-controls-20260824

Created: 2026-08-24 18:28:29
Objective: 独立审查方案全文跨章节入排控制点的领域模型、冻结目录、Agent边界、来源闭包、发布门槛及Phase 5.8实施顺序；不得把会商角色当测试者，不得修改代码或读取工作区外临床资料。
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Visual/design/HTML/PPT tasks use a Codex-led panel with no sub-venue chair. The effective visual participant chain is ``; it is filtered against the actual execution route nodes recorded below before dispatch.
- Chinese labels or Chinese sentence review is handled directly by Codex and does not start a conference.
- Other complex, logic-heavy, evidence-sensitive, artifact-heavy, code-review, and high-risk contradiction work uses a Codex-chaired panel with no sub-venue chair. Participant 1 is night Pi/Alibaba `qwen3.8-max` (xhigh) -> Pi/OpenCode Go `muse-spark-1.2-contributor` (xhigh) -> Kimi Code `k3-256k` (high) -> Codex subAgent `gpt-5.6-luna` (max), and day Pi/OpenCode Go Muse (xhigh) -> Kimi Code K3 (high) -> Codex Luna (max). Participant 2 is Cursor `auto`, with Grok Build `grok-4.6` (medium) and Pi/cms-router `minimax-m3` as fallbacks. Codex remains the final authority.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `phase5-slice58-cross-section-controls-20260824`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `AGENTS.md`：项目的临床、产品、工程与会商边界。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`：已批准的总体领域与产品设计。
- `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md`：已批准的分阶段实施顺序与验收门槛。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md`：Phase 5 当前切片、验收证据与停止条件。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260824_DNF_V1_IMPLEMENTATION_ACCEPTED.md`：当前真实模型探针入口与尚未验收边界。
- `app/domain/contracts/protocol_ingestion.py`、`app/domain/contracts/agent_io.py`、`app/domain/contracts/rules.py`：当前冻结目录、Agent 输入与规则合同。
- `app/protocols/procedure_catalog.py`：当前“基线及以前必做项目录”构建器；已观察到它只从有访视列与 X/(X) 标记的研究流程表构建。
- `app/protocols/deconstruction_service.py`、`app/agents/protocol_deconstructor.py`、`app/protocols/deconstruction_gate.py`：冻结目录到 Agent 输入、水合与发布门禁的当前路径。
- `tests/v2/protocols/test_procedure_catalog_slice3.py`及相关协议解构测试：当前确定性验收范围。
- 本轮不读取工作区外的真实方案或受试者资料；真实文件只由 Codex 在后续隔离验收中使用。

## Scope

- In scope:
  - 判断“官方 IN/EX 父规则”、“流程表必做操作”与“全文跨章节入排控制点”应否分属三类一等对象。
  - 界定跨章节控制点的范围：禁/限用药、洗脱期、合并治疗、疗效/安全阈值、评分、必做评估、过程性限制、例外与时间锚点。
  - 每个正式控制点必须能回答：审核节点是什么、需要做什么/核对什么、需达到什么条件、不能出现什么事件或暴露、时间窗/锚点、例外、最低证据、需专业判断的必要条件。
  - 同一临床控制要求可能分散在入排标准、流程表、合并用药、研究治疗、检查评估或其他章节；设计必须能区分相互补充、完全重复和实质冲突，不能只按相似文本合并。
  - 设计确定性候选发现、Agent 语义解构、人工核对、来源闭包、去重/冲突、期别/审核节点归属与发布阻断的边界。
  - 评估是扩展现有 `required_procedures`，还是新增独立的“方案审核控制点”目录及其稳定身份。
  - 给出不写死项目特异语义的分片实施顺序、停止条件和真实 D001/MG 验收要求。
- Out of scope:
  - 修改代码、数据库、真实方案、受试者资料或生产数据。
  - 视觉/浏览器终验、真实医学结论与独立测试者 UAT。
  - 把会商参与者的建议当成已验收产品事实。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.
- 明确对当前“流程表 = 全部额外控制点”假设的判断，并以代码合同为证据。
- 给出可实施的领域模型、来源闭包、完整性门禁、去重/冲突策略与中文用户呈现建议。
- 必须显式防止：把流程操作误当规则、把正文控制点与 IN/EX 重复计数、把治疗期普通操作误纳入基线前审核、把未命名时间锚点自行猜测。
- 设计能表达“应做事项”、“需满足条件”和“禁止事件/暴露”三种不同义务形态，不得将它们压成一段自由文本。

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

- 2026-08-24 18:28:29: Conference initialized by `hermes_workflow_guard.py init-conference`.
