# Conference Context: enrollment-rv1001-structural-key-recovery-20261006

Created: 2026-10-06 19:30:58 CST
Objective: 只读审阅资料整理草稿中字段名错误的通用有界恢复：仅提议JSON属性重命名，原值和全部兄弟冻结，当前来源及采用门禁保留；评估能否复用既有修复/证明/任务预算，避免又造病例特例或恢复整答。禁止原件/数据库/凭据/产品模型调用/写源码，给出最小可行或有据拒绝方案。
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

- Linked execution task: `enrollment-rv1001-structural-key-recovery-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- HEAD5dd6fc49; current owner P1 dirty is unrelated and must not be read or changed. Normalizer source under review still matches that commit.
- `app/agents/evidence_normalizer.py`: draft types, evidence_normalizer_json_schema, full parse current-draft checks, EvidenceNormalizerRunner.run and recovery helpers it actually calls. Read complete affected definitions, not the full giant file.
- `app/agents/evidence_normalizer_repair.py`: original scope freezing and preservation helpers.
- `app/agents/evidence_question_repair.py`: current short proposal / frozen composition proof (already exists, do not reinvent).
- `app/agents/evidence_candidate_partition.py`: strict initial-shape boundary and composed-answer partition; this is not permission to relax it.
- `app/agents/deepseek_evidence_normalizer_transport.py`: existing completion/proposal construction and one task repair budget.
- `app/services/fact_normalization_executor.py`: execute, failure artifact, call/proof persistence, rehydration consumers; `app/domain/contracts/facts.py` FactNormalizationCall.
- `tests/v2/agents/test_evidence_question_repair.py`, `tests/v2/services/test_evidence_question_repair_persistence.py`, `tests/v2/services/test_normalizer_candidate_partition.py`: existing synthetic recovery and consumer tests. No running tests.
- Forbidden: /Users/smkzw/tmp, clinical artifacts/originals, databases, .env, credentials, raw model output, web, product model endpoints, source writes. At most 20 material read/search actions plus 2 orientation reads; explicitly report unverified dependencies or tool overrun.

## Scope

- Owner verified one actual product failure: a valid JSON object with 88 fact candidates, one affirmative candidate assertion_basis contains keys asserted_object, assertion文本, locator_id, contextual_qualifiers, but missing assertion_text. Values and source wording were not absent; current draft preflight correctly refuses source invention before schema repair. Six previous groups saved successfully; finalization is blocked. This description contains no clinical wording and is not a gold label.
- In scope: decide whether a generic JSON-property rename proposal can recover only a unique unknown property into a missing required property, with immutable object/path/hash/value and all siblings; no guessed clinical value, enum/category change, new source, item deletion/reordering, duplicate keys or additional field aliases. Scope is current v5 draft and existing strict validators. A proposal remains unadopted until all current source/meaning validators and proof consumers pass.
- Evaluate A: reuse a bounded structural proposal under existing repair allowance; host checks actual schema, path and exact unchanged values, composes, full validates, persists/replays the proof. Evaluate B: keep this shape corruption refused, reuse successful groups, adjust task output structure only if justified. Prefer rejecting A if it cannot be source/consumer safe without disproportionate change.
- Required: identify first causal failure; concrete minimal producer/save/recovery/consumer modification, normal and dangerous counterexamples, ambiguity/technical vs clinical boundary, proof coexistence with existing classification and partition, budget accounting, recommended alternative and remaining uncertainty. No broad redesign or another framework. Do not propose literal assertion文本 aliases or model/project-specific renaming heuristics.
- Out of scope: implementation, running jobs/tests, clinical judgment, declaring entire product complete, changing automatic fact adoption standards, new providers, another queue, broad all-page rereads, arbitrary patch permissions. One fresh engineering review, not a clinical second reading.

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

- 2026-10-06 19:30:58 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
