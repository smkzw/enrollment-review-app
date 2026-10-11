# Execution Output: phase5-protocol-control-recovery-20260831 - worker_01

## Boundary And Context Check

- Implemented only the assigned minimal persisted-task resume entrance.
- No production writes or D001 replay were performed.
- Did not read or reopen the original protocol source file.
- Did not create or update the runner report artifact.

## Work Performed

Updated `scripts/run_protocol_control_smoke.py`:

- Added `--resume-job-id` CLI support.
- Added persisted control-job resume path using the existing:
  - `data_v2/enrollment-review-v2.sqlite3`
  - `JobStore`
  - `recover_expired_jobs`
  - `JobRunner`
  - protocol-control executor
- Validates:
  - existing SQLite database
  - protocol-control job type
  - persisted payload SHA-256
  - source job, snapshot, and content identity
  - required persisted source extraction/freeze checkpoints
- Reuses existing checkpoints and runs only queued/interrupted work.
- Avoids `ProtocolControlJobService.create_from_deconstruction`, new task creation, idempotency creation, fixture loading, and source-file parsing.
- Added persisted source provenance from the existing identity-confirmation checkpoint.
- Added unique resume run-record filenames when `run_record.json` already exists.
- Added CLI guards preventing resume with fixture, study-phase, read-only protocol, or missing `--out-dir`.

## Artifacts And Evidence

- Modified artifact: `scripts/run_protocol_control_smoke.py`
- Resume implementation: lines 629–905
- `run_smoke` resume dispatch: lines 924–941
- CLI wiring and guards: lines 1194–1229

Deterministic temporary-database exercise:

- Created a complete synthetic control job.
- Mutated only the temporary SQLite database to emulate an expired worker with `discovery_0001` interrupted and its checkpoint removed.
- Resume result:
  - exit code `0`
  - expired job recovered and requeued
  - final job state `completed`
  - interrupted discovery attempt advanced to `2`
  - exactly one new discovery transport call
  - zero new deep transport calls
- Resuming an already completed job produced:
  - exit code `0`
  - zero discovery calls
  - zero deep calls
  - persisted source metadata restored
  - `source_file_read=False`

## Commands And Observations

- `.venv/bin/python -m py_compile scripts/run_protocol_control_smoke.py`
  - Passed.
- `.venv/bin/pytest -q tests/v2/services/test_protocol_control_smoke_runner.py`
  - `7 passed`, 5 existing deprecation warnings.
- `.venv/bin/python scripts/run_protocol_control_smoke.py --help`
  - Confirmed `--resume-job-id` is exposed.
- `.venv/bin/python scripts/run_protocol_control_smoke.py --resume-job-id job-1`
  - Correctly rejected with exit code `2` because `--out-dir` is required.

## Blockers Or Missing Environment

- Real D001 replay was intentionally not run because this worker has no authorization for production writes or live-model execution.
- Final acceptance remains with Codex, including any live D001 decision and sibling test/review integration.

## Rerun Requests Or Next Step

- Codex should review the modified script together with the deterministic resume tests and independent boundary review.
- If approved, run the explicitly authorized D001 resume command against the existing replay directory and capture its persisted run record.
