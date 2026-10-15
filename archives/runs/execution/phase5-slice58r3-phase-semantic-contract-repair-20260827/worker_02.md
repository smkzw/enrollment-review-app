# Execution Output: phase5-slice58r3-phase-semantic-contract-repair-20260827 - worker_02

## Boundary And Context Check

Read the two declared context files. No production files, external sources, or packages were modified. Scoped edits were limited to the deterministic gate and its corresponding tests.

## Work Performed

- Restricted rule-family matching to the concrete terminal title; common ancestors no longer establish family membership.
- Distinguished target-related evidence from phase-range propagation evidence.
- Rejected ordinary title mentions and unscoped/mixed sources as propagation evidence.
- Preserved exact-title and phase-specific cross-reference behavior.
- Added three regressions for common-parent broadcast, ordinary mentions, and unscoped title anchors.

## Artifacts And Evidence

- `app/protocols/phase_applicability.py`
- `tests/v2/protocols/test_phase_applicability_contract.py`

## Commands And Observations

- Focused tests: `73 passed`.
- Compile check: passed.
- Full protocol tests: `749 passed, 9 failed, 58 warnings`.
  - 8 failures were LibreOffice render aborts (exit 134).
  - 1 failure was an existing D001 prompt-metrics mismatch in `test_slice58h_cross_heading_packing.py`.

## Blockers Or Missing Environment

The system Python lacked `sqlalchemy`; the existing project `.venv` was used successfully without installation.

## Rerun Requests Or Next Step

Parent Codex should review the scoped diff and decide whether the phase-specific cross-reference exception needs broader real-D001 validation. Final acceptance remains pending.
