# Conference Context: enrollment-rv1001-mixed-source-flow-boundary-20261006

Created: 2026-10-06 19:07:10 CST
Objective: 只读审阅既有固定流程在混合来源批次退回整wire的耦合。优先复用现有逐项目标核对、单项编译、定义依赖、受限采用与完整覆盖消费者，给出一个可实现最小方案，不新增框架，不降来源或含义标准，不把能力缺口改为研究者缺资料。禁止临床原件/凭据/库/模型业务读取/写源码或测试。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy/codebuddy-cli/deepseek-v4.1-flash:max -> zcode/zcode/glm-5.3-flash:max -> grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-rv1001-mixed-source-flow-boundary-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen HEAD 5dd6fc495304a613a4a9c56ddf17fd4a559be4f4; owner preserves inherited dirty. No adviser writes.
- `app/agents/protocol_control_fixed_flow.py`: complete definitions supports_front_stage_flow, covered_front_wire, prepare_front_stage_flow.
- `app/agents/protocol_control_stage_compiler.py`: can_compile_stage_bound_source/requirement, relative/shared prohibition preflights, compile_source_requirement_response and assemble_source_requirement_inserts, plus their directly used helpers.
- `app/agents/protocol_control_source_interpretation.py`: SourceStatement/SourceTargetReview models, target_review_indexes, validate_source_target_review, existing definition-consumer contract. Read relevant complete definitions only.
- `app/agents/protocol_control_deconstructor.py`: run branch around 6618-7080; existing independent insertion and restricted disposition consumers around 7900-8650; source_statement_coverage and referenced assembly guards. Do not read entire giant file.
- `app/services/protocol_control_execution.py`: source-only resume and save/hydrate consumers referenced by above, not the entire file.
- `tests/v2/agents/test_protocol_control_fixed_flow.py` and existing source-requirement compiler tests found under tests/v2/agents. Synthetic fixtures only. Stop if a path is absent; no raw artifact search.
- `app/domain/contracts/protocol_controls.py`: disposition and complete/restricted adoption entities used by these definitions.
- No .env, database, artifacts, logs, original protocols/cases or /Users/smkzw/tmp allowed. No web, shell execution other than bounded read/search. At most 22 material read/search actions plus 2 orientation reads. Explicitly report overrun, unavailable evidence and actual files read.

## Scope

- In scope: one engineering architecture decision: how to advance independently compilable source points inside a mixed batch while retaining complete closure, definitions, future duties and precise unsupported dimensions. Source interpretation already exists; do not reinvent it.
- Owner diagnostic of one frozen actual batch (zero model calls): 25 source statements, only indexes 7/8 currently supported by simple stage compiler; batch also has definitions, multi-period actions, after-eligibility actions, one genuine unresolved stage, exceptions and recommendations. Full FLOW preflight returns false. This counts compiler eligibility, NOT accuracy, and contains no clinical text.
- Candidate options to challenge: (A) short target review first for every point, then existing typed builders for supported additions, explicit retained capability boundaries for others; (B) split only independent owned source units using existing plan, retain all dependencies and aggregate closure; (C) keep existing baseline if neither yields consumer-complete artifacts without another truth table. Recommend the smallest warranted change, including rejecting A/B if existing contracts cannot support them.
- Out of scope: implementing code, tests, reading clinical originals, calling product models, starting jobs, publishing rules or facts, claiming clinical approval, another queue/framework or project-specific word rules. Concurrent isolated case model Job does not belong to you.
- Required answer: decisive earliest coupling with function references; what existing producer/save/consumer must be connected; normal+counterfactual+unknown/failure recovery tests; minimal concrete function-level patch or an evidenced reason not to patch. Distinguish software inability from real source ambiguity and from unfinished reading. Do not manufacture a source unresolved statement from compiler failure. Do not propose dropping successful source points or granting arbitrary parent revision permissions.

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

- 2026-10-06 19:07:10 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
