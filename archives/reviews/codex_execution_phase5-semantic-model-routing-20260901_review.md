# Codex Execution Review: phase5-semantic-model-routing-20260901

## Verdict

Accept the semantic routing slice. The implementation and deterministic routing
contracts are accepted; the live GLM probe proves semantic completeness for one
large SAR parent rule after two generic gate false positives were corrected.
This verdict does not accept current latency for a full protocol run and does
not authorize resuming the paused D001 job or mutating the failed SAR job.

## Worker Outputs

- `worker_01`: grounded the route design in the existing transport, cache and
  session contracts. Its whole-attempt fallback and no-cross-provider-mixing
  boundaries were retained.
- `worker_02`: implemented graded routing, the Coding Plan GLM transport,
  explicit auditable fallback, fresh provider attempts and pinned-mode
  compatibility. Codex repaired credential compatibility and remote scoped
  prompt/batch behavior after reopening the implementation.
- `worker_03`: added independent deterministic coverage for route order,
  short-task selection, skip/fallback audit, candidate isolation, cache identity,
  pinned mode, Chinese diagnostics and project-agnostic routing.

## Manager Assessment

No execution manager was required by the governed packet. Codex reviewed every
worker output and retained final acceptance authority.

## Boundary

Accepted scope is limited to semantic route selection, transport/fallback
isolation, generic gate corrections and one frozen read-only GLM probe. Full
protocol latency, full SAR deconstruction, clinical acceptance, subject fact
normalization, Patient Profile and browser acceptance remain outside this
verdict. The paused D001 and failed SAR jobs remain immutable.

## Hermes

The live workflow packet selected `cursor/default` for all three bounded roles.
Hermes was not used as a transport, no worker route was silently substituted,
and no fallback session was opened.

## Codex Independent Verification

- Complex route: `zhipu-coding-plan/glm-5.3-flash:high` ->
  `mtplx/mtplx-qwen38-27b-optimized-quality:medium` ->
  `deepseek/deepseek-v4-flash:high`.
- Short, single-call work: MTPLX first, then DeepSeek; GLM is not consumed for
  the default short route.
- Provider fallback creates a fresh transport and fresh semantic candidate;
  cache identity includes backend, model, effort and request contract.
- A frozen SAR EX-06 source package was sent through the real Coding Plan GLM
  endpoint without starting MTPLX or changing the source job. With a 60,000
  output-token budget it returned a complete hydrated draft in 803.21 seconds.
- The first gate result was rejected only because the generic gate ignored
  predicate-level verbatim source clauses and treated a parent lead-in plus an
  exception outcome as atomic obligations. Generic gate repairs made the exact
  same hydrated draft publishable with zero issues; model output was not edited.
- Affected regression: `238 passed, 5 warnings`.
- Full V2 regression: `3360 passed, 3 skipped, 139 warnings, 2 subtests passed`;
  one known historical D001 v1.5 prompt-hash mismatch remains and the immutable
  checkpoint was not rewritten.
- No project/study/drug/disease/time-point token is used by the route selector
  or the repaired generic gate logic.

## Cleanup Decision

After review-gate and governed execution audit pass, archive only replaceable
runner prompt/stdout/worker process files through the workflow guard. Retain
source code, tests, route manifest, review, metrics, GLM probe artifacts,
Trellis checkpoint, failed SAR job and paused D001 checkpoints.
