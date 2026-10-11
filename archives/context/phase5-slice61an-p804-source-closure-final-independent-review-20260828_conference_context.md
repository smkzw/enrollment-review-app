# Conference Context: phase5-slice61an-p804-source-closure-final-independent-review-20260828

Created: 2026-08-28 23:17:32 CST
Objective: 独立审查 p804 同源来源闭包修订合同的最终共享实现与证据边界：重点挑战来源闭包和原子 span 的互斥归一化、控制级候选闭包起点恢复、闭包外冻结、来源全集守恒、测试是否覆盖真实 runner，以及执行包审计是否正确锚定创建时路线；确认不能将工程合同可用误写为真实 v8 p804 临床通过，并判断是否具备由 Codex 决定一次新不可变语义重跑的前置条件。只读，不修改代码或临床工件，不运行模型回放，不发布控制点。
Task type: `complex_delivery_conference`
Risk: `high`
Conference mode: `serial`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
- This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `codebuddy-cli/deepseek-v4-flash:max -> codebuddy-cli/glm-5.3-flash:max -> grok-build/grok-4.6:medium -> cursor/cursor-grok-4.6:medium -> openai-codex/gpt-5.6-luna:max`; it is resolved once at packet creation and filtered against the actual execution route nodes recorded below before dispatch.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `phase5-slice61am-p804-source-closure-current-route-verification-20260828`
- Execution evidence status: `linked`
- Excluded provider/model nodes: `codebuddy-cli/glm-5.3`
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- `app/agents/protocol_control_deconstructor.py`
- `app/protocols/protocol_control_repair_errors.py`
- `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`
- Immutable rejected v8 evidence and `CHECKPOINT_20260828_V8_SCOPE_SPLIT_REJECTED.md` as historical regression anchors only.
- Round outputs under `runs/conference/phase5-slice61an-p804-source-closure-final-independent-review-20260828/`.

## Scope

- In scope: deterministic repair authority, transitive closure, mixed-issue isolation, fail-closed behavior, real-runner regressions, and independent code review.
- Out of scope: a new semantic replay, clinical acceptance of p804/p805, control publication, remaining D001 packages, subject evidence, OCR, Patient Profile, and frontend/browser work.

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

- 2026-08-28 23:17:32 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
- Round 1 found that candidate-derived source closure could exceed deterministic issue authority.
- Round 2 found that control-level findings needed an originating candidate seed.
- Round 3 accepted those fixes and found mixed repair classes could widen mutable scope.
- Round 4 accepted the final shared implementation with no remaining bounded blocker.
- Total: 822.145 seconds, 101 tool calls, one resumable session, no fallback, no replay.
