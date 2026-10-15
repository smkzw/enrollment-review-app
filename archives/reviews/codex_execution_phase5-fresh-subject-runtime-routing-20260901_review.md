# Codex Execution Review: phase5-fresh-subject-runtime-routing-20260901

## Verdict

Accept with Codex remediation. The routing and fresh-runtime boundary are ready
for the next isolated live run; this is not acceptance of the SAR 31001
clinical result or of a live provider chain.

## Worker Outputs

- `worker_01`: accepted after Codex independently checked the reconstructed
  launcher. Complex protocol semantics are GLM-5.3-Flash high -> MTPLX medium
  -> DeepSeek V4 Flash high; short new-session work is MTPLX medium ->
  DeepSeek. Provider switches use fresh transports and discard failed merged
  candidates. The real Bash launcher UAT passed 14/14.
- `worker_02`: accepted. The old `failed_final` database remains immutable and
  is refused as a new run. `sar31001-fresh` has a fresh marker and verified
  input manifests but no SQLite business state.
- `worker_03`: accepted after a same-session follow-up. Codex removed its
  duplicate `fresh_run_identity.py` surface and rebound all adversarial tests
  to the single official `fresh_runtime.py` gate. The corrected continuation
  packet passed execution audit without route drift.

## Manager Assessment

No separate manager is declared for this finite-code route. Codex reviewed all
three worker reports and the final filesystem state directly.

Hermes was not an executor, manager, transport, or acceptance authority in this
packet; no claim in this review is attributed to a Hermes result.

## Codex Independent Verification

- `audit-execution`: passed for all workers and the registered worker_03
  same-session continuation; provider/model remained `cursor/default`.
- `bash scripts/test_start_v2_uat.sh`: 14 passed. The earlier 3b failure was a
  false failure caused by forcing the Bash test through zsh.
- Focused routing/fresh-runtime checks: 40 passed; combined agent/tool checks:
  145 passed.
- Expanded `tests/v2/protocols tests/v2/agents tests/tools`: 1464 passed, one
  known immutable D001 replay checkpoint failed only because its frozen prompt
  hash predates the current prompt framework. The checkpoint was not rewritten.
- `zsh -n`, `bash -n`, `py_compile`, and `git diff --check`: passed on the
  affected surfaces.
- Fresh runtime validation re-hashed one protocol copy and five subject input
  copies. The old runtime is rejected for missing marker, existing job/event/
  checkpoint state, terminal failed job, and forbidden old job identity.
- Generic hardcoding scan found no D001/SAR/subject/disease/drug/criterion
  literal in the production router, executor, launcher, service, or gate.

Residual boundaries:
- No live GLM/MTPLX/DeepSeek semantic attempt was made in this execution pass.
- The fresh V2 service, protocol deconstruction, subject facts, Patient Profile,
  browser flow, and clinical QC have not started yet.
- MTPLX is not automatically loaded in graded mode. It remains available when
  already online or explicitly warmed with `ENROLLMENT_START_MTPLX=1`; otherwise
  a short task can explicitly skip the unavailable local candidate and continue
  to DeepSeek.

## Cleanup Decision

Archive the governed prompts, reports, and logs after the review gate passes.
Retain the review, metrics, fresh-runtime contract, input manifests, old failed
database, and clean runtime identity as durable evidence.
