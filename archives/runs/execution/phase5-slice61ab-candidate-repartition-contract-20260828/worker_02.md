Trellis SessionStart 已加载。正在读取执行上下文与计划，定位跨阶段候选重分区合同冲突。
正在创建共享门禁错误模块，并更新 replay 脚本以授权候选重分区。
# Execution Output: phase5-slice61ab-candidate-repartition-contract-20260828 - worker_02

## Boundary And Context Check

- **Role**: `worker_02` — implement precise candidate-repartition authorization in shared gate-error mapping; no final acceptance.
- **Workspace**: bound to `.worktrees/phase5-clinical-facts-profile`.
- **Initial read set consumed**: `context/phase5-slice61ab-candidate-repartition-contract-20260828_execution_context.md`, `plans/codex_execution_phase5-slice61ab-candidate-repartition-contract-20260828.md`.
- **Additional reads** (required): `runs/execution/.../worker_01.md`, `app/agents/protocol_control_deconstructor.py` (runner repartition branch L2424–2466), `slice59n_representative_group_control_replay.py` (prior `_publication_repair_error`).
- **Hard boundaries respected**: no production writes, no runner report file write, no final acceptance, no virology/project-specific hardcoding.

## Work Performed

Implemented shared publication-gate → repair-scope mapping with generic gate-code authorization for decision-stage candidate splitting.

### Root cause (from worker_01, confirmed)

`_publication_repair_error` only set `allow_candidate_repartition=True` for `ACTION_TARGET_SCOPE_MISMATCH`. For `MIXED_DECISION_STAGE_CONTROL`, the runner used 1:1 source-key replacement, silently dropping Agent split candidates with new source keys.

### Fix

1. **New shared module** `app/protocols/protocol_control_repair_errors.py`:
   - `CANDIDATE_REPARTITION_GATE_CODES` frozenset (gate-level, no project/virology terms):
     - `ACTION_TARGET_SCOPE_MISMATCH` (existing)
     - `MIXED_DECISION_STAGE_CONTROL` (primary fix)
     - `MIXED_TRIGGER_DECISION_STAGES` (same split-by-decision-stage pattern; worker_01 adjacent risk)
   - `gate_issue_allows_candidate_repartition()` helper
   - Moved `publication_repair_error`, `clinical_repair_error`, `combined_repair_error`, `replay_validation_error` from replay script into shared module

2. **Replay harness updated** `slice59n_representative_group_control_replay.py`:
   - Removed duplicated local functions (~115 lines)
   - Imports shared module with `_`-prefixed aliases for backward compatibility with existing tests

### Behavioral change

For `MIXED_DECISION_STAGE_CONTROL` (and `MIXED_TRIGGER_DECISION_STAGES`), `publication_repair_error` now sets:

```python
allow_candidate_repartition=True
```

This activates the existing runner repartition branch (`protocol_control_deconstructor.py` L2087–2128, L2424–2466), which:
- Expands `mutable_candidate_source_keys` across overlapping source unions
- Preserves all split candidates that conserve the authorized source-structure-unit union
- Routes them through hydration and publication re-check

No changes to gate detection, repair prompts, or restore logic — only the authorization contract.

## Artifacts And Evidence

| Artifact | Path / observation |
|----------|-------------------|
| Shared repair-error module | `app/protocols/protocol_control_repair_errors.py` (new) |
| Replay import delegation | `slice59n_representative_group_control_replay.py` (deduplicated) |
| Unit tests | `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py` (new, 4 cases) |
| Runner repartition consumer | `app/agents/protocol_control_deconstructor.py` L2424–2466 (unchanged, already supports flag) |

## Commands And Observations

```bash
.venv/bin/python -m pytest tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py -q
# ....  [100%]  4 passed in 0.02s

.venv/bin/python -m pytest \
  ".trellis/tasks/.../test_slice59n_representative_group_regressions.py::test_publication_repair_error_aggregates_all_affected_candidates" \
  "...::test_combined_repair_error_exposes_publication_and_clinical_scope_together" \
  "...::test_replay_validation_does_not_feed_expected_delta_back_to_agent" -q
# ...  [100%]  3 passed in 0.41s

.venv/bin/python -m compileall -q app/protocols/protocol_control_repair_errors.py
# exit 0
```

**Observations**:
- Authorization is gate-code based; no virology or D001 terms in the contract.
- `combined_repair_error` propagates `allow_candidate_repartition` from any sub-error — mixed publication+clinical errors still inherit repartition when publication side authorizes it.
- Replay script remains the product validator entry point; shared module is now the single source of truth for repair-scope mapping.

## Blockers Or Missing Environment

- **None** for this worker scope.
- **Not in worker_02 scope** (worker_03): synthetic runner regression proving old path drops candidates vs new path retains two; slice61aa artifact replay; disposition-link consistency after dual-candidate retention.

## Rerun Requests Or Next Step

### For worker_03

1. **Synthetic runner test**: `MIXED_DECISION_STAGE_CONTROL` + `allow_candidate_repartition=True` → 2 candidates hydrated + gate PASS.
2. **Negative control**: same input with `allow_candidate_repartition=False` → only 1 candidate after restore (reproduce slice61aa silent drop).
3. **Artifact replay**: `artifacts/phase5-slice61aa-virology-cross-stage-contract-20260828/execution/raw-responses.json[2]` as golden split input with fixed authorization.
4. **Scope-escape guard**: same source key → 2 candidates should still fail-closed with `REPAIR_SCOPE_ESCAPE` (not silent drop).

### Optional Codex follow-up

- Export `protocol_control_repair_errors` from `app/protocols/__init__.py` if other callers need direct import (not required for replay path).
- Consider whether `_validate_bounded_output_repair` should detect mutable-candidate count shrinkage as defense-in-depth (worker_01 adjacent risk; out of scope here).

**Resume point**: Authorization contract is implemented and unit-tested. End-to-end proof awaits worker_03 runner/artifact regression.
