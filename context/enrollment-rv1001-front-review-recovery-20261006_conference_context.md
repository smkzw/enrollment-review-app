# Conference Context: enrollment-rv1001-front-review-recovery-20261006

Created: 2026-10-06 20:02:01 CST
Objective: 只读审阅FLOW前置来源核对失败的最小局部恢复。真实路径在已有目标作用范围检查拒绝，尚无作者请求；保留完整来源与错误拒绝，不能为通过改作用范围、把技术错误变临床未决或新建证明平台。核现有validated_source_review_seed、来源核对消费者和恢复原答证明，建议有界单项核对可如何接实际保存/恢复，或有据选择暂不加恢复。只读工程与合成测试，无临床、数据库、凭据、网络、源码修改。
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

- Linked execution task: `enrollment-rv1001-front-review-recovery-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen HEAD174c3efd; no changes to these source files during this review.
- Allowed full affected definitions only: app/agents/protocol_control_fixed_flow.py; app/agents/protocol_control_source_interpretation.py (SourceTargetReview, validate_source_target_review, validated_source_review_seed, target_review_indexes); app/agents/protocol_control_deconstructor.py (ProtocolControlAgentRunner.run FLOW branch and failure result); app/services/protocol_control_execution.py (_resumable_saved_source_review, _execute_deep, validate_saved consumers); app/agents/protocol_control_agent_transport.py (source target review and existing local review methods).
- Synthetic tests only: tests/v2/protocols/test_protocol_control_fixed_flow.py; tests/v2/protocols/test_slice58c_control_deconstructor.py; tests/v2/services/test_protocol_control_execution.py. Do not run tests. Read at most 18 relevant definitions/sections, plus the two orientation files. Do not read any /tmp, artifact, clinical, env, DB or log paths.
- Owner observation, not advisor-verified clinical evidence: a 25-statement FLOW review fails TARGET_VISIT_SCOPE_UNPROVEN on index2 before author calls. Its source was classified force=required/functions=[background], but reviewer claimed complete coverage by a procedure sharing multi-visit source. Current gate correctly rejects this; no evidence to weaken the gate. The failure result drops the invalid front review and loses structured statement_index/json_path, despite actual review raw answer remaining in attempts.
- Existing validated_source_review_seed already validates siblings individually. Current proof consumer demands original full review raw identity; a host-composed review cannot pretend to be one full model answer. Partial author FLOW resume remains separately unsupported and outside this task.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: identify the first engineering limitation, evaluate the smallest reuse of existing local review/recovery/proof paths; recommend implementable scope without adding another general framework. Consider first preserving structured failed review and good siblings, then a bounded local correction, with actual raw composition proof if needed. Reject any option lacking saved/readback validation. Distinguish erroneous model proposal from true source uncertainty and compiler capability.
- Out of scope: source changes, clinical interpretation, relaxing coverage/visit/action gates, automatic adoption, whole-parent reread, author resume, new databases, network, shell writes, recursive delegation. Advice can explicitly recommend not implementing full local repair if disproportionate.

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

- 2026-10-06 20:02:01 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
