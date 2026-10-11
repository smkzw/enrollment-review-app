# Conference Context: rv1006-retained-rejection-review-20261011

Created: 2026-10-11 17:15:50 CST
Objective: 只读审阅有界来源补读与新增范围核对的生产、恢复、保存接线。被拒结果不得成为成功或临床未决；不重开无新证据的失败分支。
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

- Linked execution task: `rv1006-retained-rejection-review-20261011`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Base commit: `05fb1545` in this worktree; the current named five-file patch is the artifact being reviewed, not the seven inherited delivery-document changes.
- Read only: `app/agents/protocol_control_source_interpretation.py` (completion prompt/apply, completed_quote_review_indexes, target_review_indexes, build_source_target_review_prompt, validate_source_target_review, validated_source_review_seed).
- Read only: `app/agents/protocol_control_deconstructor.py` (run: history restoration, source completion, scoped reviewer aliases and subsequent recovery callers).
- Read only: `app/services/protocol_control_execution.py` (_resumable_saved_source_review, _validate_saved_source_review, source-only recovery); `app/services/protocol_control_restricted_source.py` (restricted consumption checks).
- Read only: `tests/v2/services/test_protocol_control_execution.py` (test_source_unit_completion_ranges_preserve_antecedent_and_adjacent_actions and test_completed_source_quote_schedules_the_same_scope_at_production_and_save).
- Read only as needed: `app/agents/protocol_control_fixed_flow.py`, existing source-review tests in `tests/v2/protocols/test_slice58c_control_deconstructor.py`.
- Authoritative requirements: retain literal antecedent/action separation, siblings unchanged, complete source capture, expanded source independently reviewed before saving or faithful restricted consumption. No model output is adoption; no failed output becomes researcher judgment.
- Runtime evidence limited to metadata: first diagnostic 1 call/18.725s failed on swallowed antecedent; next diagnostic 2 calls/22.496s captured source but save rejected because review selection omitted the expanded general-disposition item. Both retained and DB hash unchanged. These are product-harness read-only diagnostics, not persisted product jobs or clinical acceptance.
- Connected regression window: 79 passed/1673 deselected/5 SWIG warnings, exit 0. First run 78 passed/1 failed due owner synthetic history fixture missing mandatory receipt fields; fixed fixture, not gate. JUnit `artifacts/rv1006-completed-range-review-connected-20261011-v2.xml`.
- No reading `.env`, raw clinical files, database, private raw model replies, unrelated artifacts or local temp directories. Do not scan the repository wholesale.

## Scope

- In scope: find concrete producer/consumer scope mismatches, skipped reviews, stale review reuse, invalid history promotion, shared-budget reset or legal normal-case rejection. Check both baseline and optional fixed-flow callers where relevant. Propose the smallest coherent correction, not a new framework.
- Out of scope: clinical interpretation of real source text, new models, generic queues, full project redesign, raw data, Git operations, writes, final acceptance. Retaining rejected candidate-alignment failures was the initial packet topic but has not been implemented; do not claim to review that nonexistent patch.

## Success Criteria

- Each selected primary route returns an auditable output or an explicit health/fallback reason.
- The prompt uses the correct Agent identity, provider/model, effort, tools-enabled policy, and same-session continuation policy.
- The runner records session, usage/tool observations, fallback decisions, and failure reasons without `--max-turns 1`.
- No runtime data or source file is modified; Codex retains final acceptance. State exact code evidence and at least one safe normal case and dangerous counterexample. Distinguish confirmed bug from concern and unperformed test.

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

- 2026-10-11 17:15:50 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
