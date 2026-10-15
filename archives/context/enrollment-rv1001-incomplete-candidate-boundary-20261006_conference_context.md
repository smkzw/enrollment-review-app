# Conference Context: enrollment-rv1001-incomplete-candidate-boundary-20261006

Created: 2026-10-06 22:26:44 CST
Objective: 只读核对：规范值缺失候选能否沿既有局部隔离保留为来源待核，以及旧成功范围合法恢复的最小边界；不得改临床事实或建议重新整例盲读
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

- Linked execution task: `enrollment-rv1001-incomplete-candidate-boundary-20261006`
- Execution evidence status: `no linked execution packet`
- Excluded route identities: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. The complete agent/provider/model boundary is retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Frozen base HEAD deac747cf9de8ce84534d21e536f78f72fb67093. Owner dirty P1 prompt/test files are unrelated and excluded.
- Source definitions: app/agents/evidence_candidate_partition.py (whole 272-line module); app/agents/evidence_normalizer.py (_hydrate_draft and EvidenceNormalizerRunner.run only); app/domain/contracts/facts.py (ClinicalFactCandidateV2 only); app/services/fact_normalization_executor.py (_load_run_authority, _validated_checkpoint_output, _validate_partition_receipt definitions as actually named); app/services/fact_normalization_job_service.py (create_from_source only, actual signature).
- Read named definitions with available read/search tools; one adjacent called definition per question permitted. No broad file dump, shell, tests, directories, credentials, database, clinical originals or private artifacts.
- Actual isolated job on this frozen code took 854.811s, six successful source groups/251 candidates, seventh failed, 0 clinical facts. It stopped after original source-object error, then missing canonical_value in repair; partition of the original also failed for missing canonical_value. First original request 100.281s/43081 output tokens, repair 51.048s/20681 output tokens; actual request/response hashes and job/run/call/step bindings verified by owner. Original and old terminal hashes unchanged. This is a different first error from previous assertion field-name failure, not endpoint failure or clinical absence.

## Scope

- In scope: judge a bounded software change that retains a source-bound, well-formed but incomplete fact candidate as a concrete unresolved item, never an adopted fact; keep all source/identity/global-shape constraints. Identify downstream proof/version/current-run consumers before recommending code. Also identify the smallest lawful way to preserve six successes when only quarantine validation changes, without impersonating new reads or changing the failed final state.
- Out of scope: product reading, clinical judgment, publication, edits, more models, another framework, another complete-case rerun, accepting missing values as facts, weakening global source gates.

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

- 2026-10-06 22:26:44 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
