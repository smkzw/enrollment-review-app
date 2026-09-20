# Conference Context: written-judgment-scope-20260910

Created: 2026-09-10 00:47:25 CST
Objective: 只读审阅正式研究者书面判断来源覆盖合同，区分已核实阳性证明、未核实与完整范围缺失，给出最小可实施方案，不改代码不调用产品模型
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3:max -> xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `written-judgment-scope-20260910`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Initial read: app/projections/written_judgment_evidence.py; app/services/evidence_expectation_projection_service.py; app/projections/evidence_expectations.py; app/domain/contracts/evidence_expectations_v2.py; app/services/fact_normalization_executor.py; tests/v2/projections/test_written_judgment_evidence.py; tests/v2/services/test_expectation_document_categories.py; tests/v2/projections/test_evidence_expectations.py. Adjacent schema/repository/harness source and relevant synthetic tests may be read to trace actual callers. Do not inspect raw clinical artifacts, databases, secrets, home config or other projects. No network or product model calls.
- User rule: absent explicit protocol thresholds, written investigator assessment only from report annotations or corresponding review-node chart analysis. An abnormal flag alone is insufficient. If both models establish absent written judgment for an item, report cannot determine eligibility due to missing judgment; do not stop the workflow asking user to confirm absence. An unread/unverified note is NOT evidence of absence. Final medical acceptance remains false.
- Do not add production paths unless the user explicitly authorized reading them for this task.

## Scope

- In scope: read-only challenge of positive and negative source coverage, target/time/node binding, printed clinical analysis versus handwriting, multi-model uncertainty, user-facing outcomes; propose smallest implementation and decisive synthetic tests. Owner ran the three named test files:57 passed. Independently inspect the actual logic rather than trusting test count.
- Out of scope: edits, dependency installation, production execution, direct clinical data review, automatic source reinterpretation, delegation. Review is engineering/contract advice, not medical signoff. No need to create a new ontology or rerun all pages. Recommend reuse existing immutable source/coverage/reconciliation contracts and bounded semantic tasks. Identify any fixes possible without invalidating old accepted source versions. Distinguish immediate confirmed defects from future extensions, including whether matching only asserted_object on CS/NCS can misapply a judgment to a different measurement/time despite shared page.

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

- 2026-09-10 00:47:25 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
