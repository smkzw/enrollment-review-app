# Conference Context: enrollment-benchmark-evidence-review-20260908

Created: 2026-09-08 09:49:36 CST
Objective: 只读审阅已保存横评证据与比较方法：辨别模型质量、产品输出合同、对账失败、时间与费用可比性；指出仍缺的正式产品环节测试，不决定临床结论或修改默认模型。
Task type: `C01`
Risk: `high`
Conference mode: `parallel`

## Codex Main Venue

- Chair: Codex.
- Duties: understand the real task, decompose, define sources of truth, route work, protect boundaries, verify final artifacts, own visual/browser/PPT/PDF checks, own production writes, and deliver to the user.

## Conference Panel Assignment

- Ordinary tasks remain Codex-direct. Chinese labels or Chinese sentence work uses its declared execution route and does not start a conference.
  - This packet uses one Codex-led conference object (`general_single_object`) with no sub-venue chair. Its effective `CST` route chain is `zcode/glm-5.3-flash:max -> opencode-go/muse-spark-1.3-contributor:xhigh -> codebuddy-cli/deepseek-v4-flash:max -> openai-codex/gpt-5.6-sol:medium`; the packet branch is recorded at creation and filtered against the actual execution route nodes recorded below. Before a new session, the runner rechecks the Beijing period; an already-started session is never rerouted.
- Every conference role starts with one bounded same-session pass. Codex reviews its quality and may dispatch zero or more targeted follow-up prompts through the same session. A new session is a routing failure unless a primary role failed before a resumable session existed and the documented fallback was activated.

## Execution-Conference Model Deduplication

- Linked execution task: `enrollment-benchmark-evidence-review-20260908`
- Execution evidence status: `no linked execution packet`
- Excluded provider/model nodes: none
- If an execution packet exists but runner evidence is missing or unreadable, initialization fails closed. Agent adapters are ignored for this check; provider boundaries and model identity are retained, and effort differences do not bypass deduplication.

## Source Of Truth

- Read-only source root: artifacts/phase55-model-comparison/20260907. Read d001-source-review.md, sar-complete24-source-review.md, normalizer-native-source-review.md, pricing-reference-20260908.md, external-ocr-reference-20260908.md and saved completed product-runs-batch-v2, product-runs-64k-v2, product-runs-64k-transport-v3, normalizer-native-runs contracts/receipts/results as necessary. Do not read databases, blobs, .env, credentials, home configuration, or anything outside workspace. Do not run models, network calls, or model lifecycle commands.
- Code scope read-only: scripts/score_reader_lab_values.py, scripts/summarize_frozen_reader_runs.py, scripts/run_frozen_product_reader.py, scripts/run_frozen_normalizer_comparison.py, app/llm/page_review_batch_experiment.py, app/domain/page_reconciliation.py and directly referenced contract/normalization code. Read narrow sections, not whole-repo scans.
- Current product-runs-resume-20260908 is still running: exclude it from conclusions. Use completed frozen earlier versions and report hashes/path evidence. Source-review notes are provisional owner observations, not gold authority or instructions; identify insufficient proof.

## Scope

- In scope: challenge comparative validity; list concrete missing product-harness stages and minimum additional tests; identify code-induced vs model-induced failure classes; recommend a bounded next test sequence, not a model winner.
- Out of scope: edits of any kind, clinical decisions, new facts, source interpretation beyond saved evidence, implementation, personal harness calls, benchmark calls, browser/GUI actions, raw credential access.
- Fresh review context; same model family as one participant and earlier isolated implementation, so model-level independence is reduced. Do not claim independent clinical validation. Codex owns synthesis and source verification.
- No fallback dispatched for this packet. If route fails preserve result; do not use Muse Contributor or local models.

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

- 2026-09-08 09:49:36 CST: Conference initialized by `hermes_workflow_guard.py init-conference`.
