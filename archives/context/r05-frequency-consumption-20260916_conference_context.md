# Conference Context: r05-frequency-consumption-20260916

Created: 2026-09-16 00:44:38 CST
Objective: 仅只读源码设计审阅：按R3及设计文末频次边界，核现有OccurrenceWindow与正式候选/资格/命题/观察任务，提出最小完整的频次生产消费接线，区分汇总次数、逐次事件、发生天数及滚动与固定范围。不得写代码、测试、应用导入、数据库、浏览器或产品模型；owner整合。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> pi/openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r05-frequency-consumption-20260916`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md: 17节及文末频次源码边界；plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md: T3/T4。
- app/domain/contracts/rules.py: OccurrenceWindow/AtomicPredicate；app/domain/expression.py: _evaluate_atomic。
- app/domain/contracts/facts.py: ClinicalEventV2/clinical_event_stable_identity；app/services/fact_publication_service.py: _publish_events；app/services/source_reference_successors.py。事件稳定合并键不证明实际次数。
- app/domain/contracts/control_evaluation_spec.py；app/projections/control_operand_calculation.py。
- app/services/proposition_evidence_input.py、predicate_proposition_calculation.py、qualified_proposition_evidence.py；app/llm/proposition_evidence.py、proposition_context.py；app/domain/contracts/proposition_evidence.py。
- app/services/observation_relation_input.py、observation_relation_receipts.py、qualified_observation_relation.py；app/domain/contracts/observation_relation.py。可按具体依赖展开相邻定义，不读raw病例/凭据/历史日志。
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: 源码确认缺口，给出最小完整频次来源合同/数据生产/计算/方法批准/报告的实施顺序及反例；不要求列测试代码。适用于任意方案/药品/疾病/模型。
- Out of scope: 一切写入、测试、应用导入、对象构造、服务/数据库/模型/浏览器、重新架构主队列、产品模型横评、改变历史身份和默认模型。无需联网，源码需求足以分析；非临床验收。

所有者待审取舍：先支持原文直接记载的总次数/发生天数并核期间，再支持逐次原文的同次/异次关系及代码计数；汇总不能与明细相加，不虚构事件。现OccurrenceWindow仅duration/minimum_count，若不足应有原文支持的范围/量词声明，不用机械默认补齐。提出可复用现有双路任务的最小接线，但不能把数值频次伪装为普通语义entails。原比较、外层回溯窗及滚动/固定窗各自明确，未提供记录不等于未发生。用户允许基于本次所供且核对资料判断，不额外索取全部资料声明；已知缺失保留。最近原文未来声明消费已存在，不重复施工。

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No production path is read or modified; Codex retains final acceptance.

## Conference Pass Rule

This packet uses one serial Codex-led conference object. Each declared role receives one complete prompt and may use multiple internal tool turns. Codex decides whether a same-session follow-up is needed after reviewing the result; follow-ups do not create a new conference or change the route identity.

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

- 2026-09-16 00:44:38 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
