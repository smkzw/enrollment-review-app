# Conference Context: enrollment-pair-important-evidence-20260908

Created: 2026-09-08 14:11:15 CST
Objective: 独立审阅冻结真实原件与远端加远端、远端加本地双模型结果，核查数值互补不等于临床可靠、手写评分及缺失信息边界；不得运行产品模型或修改文件。C02已因ALL_TARGETS_SKIPPED失败，此为重要证据审阅，不替换参试者。
Task type: `C03`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`evidence_single_object`) with no sub-venue chair. Its effective `CST` route chain is `xai/grok-4.6:high -> xai/grok-4.6:high -> openai-codex/gpt-6-astra:low`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-pair-important-evidence-20260908`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read-only source root: artifacts/phase55-model-comparison/20260907/.
- Allowed frozen inputs: product-input-v2/{input.json,manifest.json,pages/}; product-source-d001-sa07007-v1/{input.json,manifest.json,pages/}. Inspect original images, not OCR alone.
- Allowed completed records: product-runs-complete24/; product-pair-gemini-main-a-20260908/; product-runs-resume-20260908/minimax-m3-high-page-{9,17}/; product-runs-muse-authorized-20260908/ (all eight runs complete); product-runs-mlx-serve-20260908/default-{low,high}-page-{9,17}/ and d001-default-{low,high}-page-42/, d001-default-high-page-44/; product-runs-64k-transport-v3/d001-glm-high-page-{0,42,44}/.
- Allowed comparison artifacts: pair-numeric-slices-20260908/, pair-muse-authorized-20260908/, pair-mlx-serve-20260908/; gold-sar-lab-page9.json, gold-sar-biochemistry-page17.json. Gold is fallible: challenge it against the original. Do not read main-thread narrative findings or reports.
- Allowed code: scripts/score_reader_numeric_pair.py, scripts/score_reader_lab_values.py, app/domain/page_reconciliation.py, app/domain/page_source_association.py, app/domain/targeted_page_review.py and their direct contract/normalization dependencies.

## Scope

- In scope: independently inspect SAR images 9/17 plus one clinical narrative page, D00142/44 originals; compare actual observation records and product reconciliation; identify common errors, selective extraction, handwriting ambiguity, unit/time/negation loss, false correspondence and gold-assisted versus product-accepted recall. Compare local+remote and remote+remote without choosing by accepted-key count. Cite page and observation IDs, distinguish observed from inferred, recommend smallest general remedies and decisive further tests. You may explore within the allowed frozen set beyond the listed examples.
- Out of scope: all file modifications, any model/API calls, credential/configuration access, networks, production databases, other workspaces, recursive delegation. Do not read MODEL_COMPARISON, harness-findings, other reviewers or main-thread conclusions. You are an adviser, not the product reader or enrollment decision maker. If original-image tools fail, disclose that; do not substitute text-only inspection and call it visual review.
- Delivery: return one detailed Chinese report with high-impact findings, actual evidence inspected, uncertainties, pairwise interpretation, and actionable recommendations. The runner saves it. Do not write a file.
- Runtime: connectivity passed on grok-build/grok-4.6:high, no fallback. This dispatch freezes that primary route; no automatic alternative model. Earlier generated fallback prose is superseded for this dispatch. Reviewer model differs from tested candidates, but this is not professional sign-off.

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

- Follow-up source_correspondence: same session/route, read-only scope additionally permits alignment-mlx-d00142-20260908/{page-0.json,page-0-request.json,posthoc-source-correspondence.json}, scripts/evaluate_observation_alignment.py and tests/v2/services/test_observation_alignment_experiment.py. Challenge the posthoc field-identity labels against the already allowed original image. No product acceptance, no edits, no API calls or new workers; do not read aggregate owner reports. This is not authority to relax matching constraints.

- 2026-09-08 14:11:15 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
