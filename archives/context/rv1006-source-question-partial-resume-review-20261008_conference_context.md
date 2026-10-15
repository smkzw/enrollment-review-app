# Conference Context: rv1006-source-question-partial-resume-review-20261008

Created: 2026-10-08 13:38:33 CST
Objective: 只读挑战已保存草稿中的剩余来源疑问能否单条继续核对、旧核对资格及修复预算边界；不读取病例、不改源、不执行产品模型。
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

- Linked execution task: `rv1006-source-question-partial-resume-review-20261008`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen source HEAD f205bf54. No application patch yet. Inherited seven delivery files are unrelated and excluded. Do not read clinical originals, private data, environment files or old conferences. Read/search only the five paths below, at most ten substantive source reads. Return a short evidence-based recommendation; no tests, edits, models, web or recursive dispatch.
- Allowed source: app/agents/protocol_control_deconstructor.py (run around 6920-7635, source-review reuse identity and filter, repair identity); app/agents/protocol_control_source_interpretation.py (source scope question prompt/apply/selection, target review validation); app/services/protocol_control_execution.py (_validated_deep_partial_source and source seed proof); tests/v2/protocols/test_source_time_question_recheck.py; tests/v2/protocols/test_slice58c_control_deconstructor.py (saved wire and review resume fixtures only).
- Sanitized actual observation: six frozen table statements. Four early statements and final statement have missing native-column scope questions. Shared repair allowance is four, consumed by four scoped source proposals. Author then runs, target review retains the final question and the group fails. Four proposals remain saved. Earlier fifteen completed groups reused with zero calls; later independent group completed. Not an unavailable model or true clinical ambiguity proven. No clinical publication.
- Proposed smallest change to challenge: remove `not resuming_partial` from the source question block so that an already gate-valid saved wire may retain its unrelated content while an eligible remaining source question receives the existing one-statement SourceInterpretation proposal. Exact quoted text, source identity, force, exception and all siblings stay frozen. Native scope only through existing all-marked-columns guard. Existing `_source_statement_reuse_identity` and full source/coverage/target/final validators must invalidate the changed item's old review. Do not automatically adopt or mutate the saved wire, clear uncertainty, add a patient requirement, or trust old complete target review after a source change.
- Source-only proof replay of a resumed original inventory is distinct from proving a saved wire under unchanged components. Identify whether the proposal requires changes to actual persistence/recovery consumers; no global prompt/compiler upgrade or version whitelist. If it cannot safely retain the wire, state the precise existing consumer that must reject it and the minimum alternative. User waived testing request caps; old budgets and ledgers retained, no scope reset by new directory.

- TODO: Add authoritative local files, extracts, datasets, screenshots, URLs, or user-provided materials.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- One question only: can the existing source-question and reviewed-wire path safely continue the remaining source question? Challenge cache/review qualification, same-session state, budget accounting, and failure preservation. Recommend exact minimal edits and targeted positive/negative consumer checks. Do not redesign the product or repeat broad strategic reviews.

- In scope: TODO
- Out of scope: TODO

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

- 2026-10-08 13:38:33 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
