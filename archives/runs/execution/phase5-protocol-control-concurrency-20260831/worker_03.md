Executing the assigned concurrency-acceptance work. Reading the authorized context and plan first.Context is sparse on source-of-truth paths. Locating JobRunner/JobStore and any parallel-execution surfaces to design the acceptance tests.Found JobStore under `app/workflow`. Inspecting the runner/store and how discovery batches execute today.Uncommitted workflow changes look like the parallel surface. Diffing those next so acceptance tests can target the real contract.Designing and adding an acceptance suite that targets the intended parallel contract, with serial baselines that can run against the current runner.Writing the acceptance suite and running baseline probes against the current serial runner.Verifying snapshot/event field shapes, then running the acceptance suite.Adding always-on serial semantic acceptance cases for cancel, failure, lease loss, and recovery so those scenarios are executed now.Repairing the corrupted graph test body.Recovery failed because discovery steps default to `max_attempts=1`. Raising attempts so interrupted steps can requeue.Fixing the skipped parallel recovery case so it won't fail on attempt budget once the API lands.# Execution Output: phase5-protocol-control-concurrency-20260831 - worker_03

## Boundary And Context Check

- Read initial set:
  - `context/phase5-protocol-control-concurrency-20260831_execution_context.md`
  - `plans/codex_execution_phase5-protocol-control-concurrency-20260831.md`
- Additional evidence reads (needed because Source Of Truth was TODO):
  - `app/workflow/runner.py`, `app/workflow/jobstore.py`, `app/workflow/recovery.py`
  - `app/services/protocol_control_execution.py` (discovery step graph / payload freeze notes)
  - `tests/v2/workflow/conftest.py`, existing workflow tests
- Scope kept to assigned item only: design + execute concurrency acceptance; no peer-report review; no clinical/regulatory acceptance; no production writes; no package installs.
- Assumption: writing `tests/v2/workflow/test_controlled_parallel_acceptance.py` is the authorized artifact for this work item.

## Work Performed

1. Established current contract baseline:
   - Discovery batches are already created **without** inter-batch `depends_on`; only `closure` joins them.
   - Durable `JobRunner` still advances **one** runnable step at a time (`next_runnable_step`).
   - Payload still records: `"Current durable runner remains serial within one job."`
   - No `JobRunner` constructor param among candidates: `max_in_job_parallelism` / `max_parallel_steps` / `in_job_parallelism` / `max_parallel_discovery_steps`.

2. Designed and added acceptance suite:
   - Artifact: `tests/v2/workflow/test_controlled_parallel_acceptance.py` (17 tests)
   - Always-on coverage: fake-concurrency serial peak, graph independence, anti-overfit scan, partial success, retryable failure, cancel, lease loss, recovery, serial compatibility.
   - Parallel-gated coverage (skip until API exists): peak==configured max with real barrier overlap, completion-order vs monotonic events, parallel partial/retry/cancel/lease/recovery, `max_parallel=1` serial mode.
   - Capability gate intentionally **fails** if parallel API is absent (prevents mistaking serial for parallel).

3. Executed acceptance + related workflow baselines.

## Artifacts And Evidence

- **Created:** `tests/v2/workflow/test_controlled_parallel_acceptance.py`
- **Evidence (acceptance):**
  - `.venv/bin/python -m pytest -q tests/v2/workflow/test_controlled_parallel_acceptance.py`
  - Result: **`1 failed, 8 passed, 8 skipped`**
  - Failed (expected gate): `test_parallel_capability_gate_is_present` — no in-job parallel JobRunner param.
  - Passed serial semantics:
    - peak concurrency for independent discovery-shaped steps == **1** (anti-fake-concurrency baseline)
    - discovery graph independence + closure join
    - no project-specific markers (`D001` / `CMS-D001` / `SAR…`) in workflow + protocol_control_execution paths
    - fatal partial success keeps prior checkpoints
    - retryable failure re-runs only failed scope
    - cancel between independent discovery steps
    - lease loss does not forge `step_failed`
    - recovery requeues interrupted discovery and avoids replaying completed discovery
  - Skipped 8 true-parallel scenarios pending worker_02 API.
- **Evidence (workflow regression baseline):**
  - `.venv/bin/python -m pytest -q tests/v2/workflow/test_runner.py tests/v2/workflow/test_recovery.py tests/v2/workflow/test_prepared_step_result.py`
  - Result: **`24 passed`**
- **Inference:** claiming task-internal parallel discovery today would be **假并发**; graph is parallel-ready, runner is not.
- **Uncertainty:** exact worker_02 parameter/config-freeze field name is not yet present; suite ducks common names.

## Commands And Observations

| Command | Observation |
|---|---|
| Inspect `JobRunner.__init__` signature | No in-job parallel knob |
| `rg` lease/parallel in workflow + protocol_control | Serial runner; discovery steps independent; payload note still serial |
| Overfit `rg` for D001/CMS-D001/SAR in workflow + protocol_control_execution | No matches |
| Acceptance pytest | `1 failed, 8 passed, 8 skipped` |
| Workflow baseline pytest | `24 passed` |

## Blockers Or Missing Environment

1. **Hard blocker for true parallel acceptance:** worker_02 has not landed a discoverable, lease-safe in-job parallel API on `JobRunner` (and config freeze). Until then, peak/overlap/order/cancel-cohort parallel cases remain skipped; capability gate remains red by design.
2. Context Source Of Truth was TODO; no Codex-named authoritative parallel contract beyond the objective text.
3. Codex question: confirm the frozen parallel knob name (`max_in_job_parallelism` vs alternatives) and whether payload should freeze `parallel_execution` so the acceptance detector can pin to one API.

## Rerun Requests Or Next Step

1. After worker_02 lands lease-safe parallel + freeze: re-run  
   `.venv/bin/python -m pytest -q tests/v2/workflow/test_controlled_parallel_acceptance.py`  
   Expectation: capability gate green; previously skipped 8 cases executed; no peak>configured; no fake concurrency.
2. Optionally align detector to the final parameter name if different from candidates.
3. Codex remains final authority for acceptance; this worker does not claim completion of the overall concurrency objective.
