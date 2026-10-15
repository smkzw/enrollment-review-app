# Conference Context: rv1006-feedback-hydration-review-20261007

Created: 2026-10-07 11:30:10 CST
Objective: 只读审阅局部语义修订重装丢失兄弟来源核对引用的最小修复：完全未变组件及映射保留旧引用，选中目标不继承；来源核对仍按完整父条basis重验。不读临床、库或凭据，不改文件。
Task type: `C03`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `grok/grok-build/grok-4.7:high -> pi/cursor/grok-4.7-high:high -> pi/openai-codex/gpt-6.1-sol:high`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `rv1006-feedback-hydration-review-20261007`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- HEAD 1e5f3e35；生产源码未改，两个测试文件有新增回归。本轮是修复前设计审阅，不是假称已实现。
- app/agents/protocol_deconstructor.py SHA256 e353b2031faf5485d1e6a31a7a9b56845373b3660e21acc79f6145b4ae76039e
- app/protocols/official_scope_review.py SHA256 12fddecee262cf72f0f087e182a6a2127ecfe782a8fa9b884ee78351e7be47e3
- app/services/protocol_workbench_service.py SHA256 8dfe91aadbf975fde05475c016386bd50aec80627173e05cec572149f8120e11
- tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py SHA256 278f0c11413f0d297a35fb8877cb95946443d7ca5f722ff68d0fd5b962d4c522
- tests/v2/protocols/test_official_scope_review.py SHA256 c633e8e0e7b4fdabec90719d6b80d0ba3629e05020bebed8522cbfdf94295d5f
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: 完全未变兄弟核对引用保全的充分边界、重装共享对象及实际作用域/门禁消费者、合成反例。
- Out of scope: 模型临床读取、真实原件、tmp目录、数据库、环境/凭据、源码修改、运行测试或Git、网络、递归派发、规则采用与签发。

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

- 2026-10-07 11:30:10 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
