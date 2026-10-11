# Conference Context: r01-r5-recovery-review-20260913

Created: 2026-09-13 16:20:23 CST
Objective: 只读审阅R01 r5失败证据与下一步最小恢复方案，区分来源语义、900秒超时、长事务；不修改产品、不调用临床模型，不把候选当采信。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.6:high -> pi/cursor/cursor-grok-4.6:high -> codex-subagent/codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `r01-r5-recovery-review-20260913`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- 当前worktree docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md §17.1.1；plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md T1。
- artifacts/review-20260912/r01-binding-probe-20260913-r5/{job.json,result.json,read-audit.json,runtime-contract.json}；其中data/artifacts/raw_response为内容寻址原请求/回答/候选。只读本目录内材料，不读工作树外临床原件。
- app/services/predicate_binding_job.py、app/services/predicate_binding_input.py、app/llm/predicate_binding_candidates.py、app/llm/page_review_harness.py、app/workflow/runner.py、scripts/run_predicate_binding_probe.py及对应tests/v2。
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: 独立验证失败原因；评价只补失败步骤的恢复契约、来源与语义对应限制、900秒非流式等待与长事务成本；给出最小可测试方案及不能采信之处。结论附代码/工件路径，不展开无关大重构。
- Out of scope: 不写任何文件/数据库；不运行模型、修改参数、读凭据或重跑；不自动认可候选，不审核用户入组，不以缺一批声称全量质量合格。

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

- 2026-09-13 16:20:23 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
