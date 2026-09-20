Continuation round 4 — verifying each of my F1-F6 findings against the current code. Reading all assigned files.

F2, F4, F6 implemented in the harness (cross-checks, duplicate-ref rejection, toolchain provenance). Now the CLI, repair errors, deconstructor, and tests.

F1 addressed (verify-pack now requires expected fingerprint; `--out-dir` enables rebuild-from-committed-config). Now the committed checkpoint files.

Committed config is durable and repo-relative. Now the checkpoint fingerprint file.

F1 checkpoint is complete and committed. Now F3 — structured error-class provenance in `protocol_control_repair_errors.py`.

F3 structural provenance present in all three construction sites. Now the deconstructor side — `error_class_codes` param and `_error_class_codes` consumption.

F3 closed (structured, no text parsing). Now the updated tests.

The D001 checkpoint rebuild is now a committed regression test. Reading the remainder and the first part of the test file for the duplicate-ref and cold-import tests.

F4, F5 tests present. Checking the budget-contract test updates and whether a toolchain provenance test exists.

Toolchain regression present. Now the updated budget-contract test expectations.

Budget tests updated to the structured provenance. Verifying the test helper and re-confirming no D001 hardcoding entered the harness.

Helper isolates the identity cross-check from hash tamper detection. Final grep: no D001/p803 leakage into product code.

Harness/repair-errors/deconstructor clean of project-specific anchors. One last count check on the budget tests.

All checks complete. Writing the final updated report.

# Conference Participant Output: phase5-slice61ap-replay-harness-budget-independent-review-20260829 - general_single_object (continuation round 4)

## Boundary Check

- Read-only review of the post-fix files in the assignment, plus the linked execution provenance read earlier in this same session. No edits, no model calls, no control publication, no production paths.
- Bash remains permission-denied here, so recorded test counts (focused 73 passed; suite 1033 passed, 58 warnings; D001 double-build fingerprint `cdb75fbc…`) are quoted as recorded evidence, cross-checked against the committed checkpoint values I read — not independently executed. That is the only unverified claim.
- Did not look at other participant outputs.

## Independent Work Product — F1–F6 verification (round 4)

**Verdict: F1–F6 are all CLOSED.** Each finding is implemented in the actual code and regression-locked by tests; the D001 anchor remains a test-only artifact, not a shared product rule.

**F1 — durable external checkpoint: CLOSED.** Committed `p803-p805-model-free-replay-config.v1.json` (repo-relative doc path, expected SHA, owned p803–805, 7 attached refs, pinned time, empty human targets, "不代表临床验收" note) and `p803-p805-model-free-replay-checkpoint.v1.json` (expected fingerprint `cdb75fbc…`, identities, toolchain, `model_invoked: false`, `clinical_acceptance: false`). New regression `test_d001_p803_p805_read_only_checkpoint_rebuilds` rebuilds from the in-repo DOCX and asserts identities + fingerprint + `verify(..., expected_fingerprint) == []`. CLI: `--verify-pack` now hard-requires `--expected-fingerprint`; new `--out-dir` override enables rebuilding the read-only config into a temp dir; `build_protocol_replay_pack` now honors `config.base_dir` (also closes the CWD-relative-path footgun).

**F2 — identity cross-checks: CLOSED.** `verify_replay_pack` now validates `replay-input.json` (schema + config-echo vs summary for sha/artifact/version/phase/owned/attached refs; source_artifact id/sha; doc sha; created_at; toolchain); cross-checks manifest identity fields, snapshot identity + parser toolchain, batch identity (`batch_id`, `coverage_manifest_id`, `protocol_version_id`, `study_phase`), owned/attached closure in refs AND unit ids, byte-identity of every batch unit against the manifest, and `agent-input.json == ProtocolControlAgentInput.from_batch(batch)`. Parametrized `test_verify_cross_checks_saved_contract_identities` tampers each file (summary hash re-anchored) and asserts the exact mismatch strings.

**F3 — structured error-class provenance: CLOSED.** `ProtocolControlAgentWireValidationError` carries `error_class_codes` (outer code auto-prepended, deduped); `publication_repair_error`/`clinical_repair_error` pass `[issue.code ...]`; `combined_repair_error` flattens all active codes; `_error_class_codes` returns `sorted(error.error_class_codes)` — the free-text regex is gone. Budget tests updated to mirror it.

**F4 — duplicate source_ref rejection: CLOSED.** `_unit_by_source_ref` raises on manifest-internal duplicates; `test_duplicate_manifest_source_ref_is_rejected` locks it.

**F5 — cold-import transport isolation: CLOSED.** `test_cold_import_does_not_load_model_transport` subprocess-cold-imports the harness and asserts transport/llm/openai/httpx/requests absent from `sys.modules`.

**F6 — toolchain provenance: CLOSED.** `toolchain {python_version, pydantic_version, parser_name, parser_version}` recorded in replay-input and summary, cross-checked in verify (including snapshot parser fields), asserted in the first test, and recorded in the checkpoint.

**Invariants re-confirmed:** global budget 2 + no-progress stop; byte-reproducible pack; model-free default; PDF explicitly rejected and PDF-to-structure still not delivered; no clinical result accepted; no D001/p803/p805/matrix/`span-*` in the harness, repair-errors, or deconstructor (grep-verified).

## Evidence And Assumptions

Read this round: `protocol_replay_harness.py` (verify body, `_unit_by_source_ref`, toolchain, base_dir), CLI, `protocol_control_repair_errors.py`, deconstructor (`__init__` + `_error_class_codes`), both checkpoint JSONs, both test files (18 harness tests incl. 4 new; 5 budget tests updated). Assumption: the in-repo venv (Py 3.12, pydantic 2.13.3) matches the checkpoint toolchain — required for the D001 rebuild test to pass and consistent with the recorded counts.

## Risks, Gaps, And Verification Needs

No remaining blocker. Residual boundaries (not defects):
1. **Toolchain coupling of the checkpoint fingerprint:** a python/pydantic upgrade deterministically breaks the D001 checkpoint regression until deliberately re-anchored (re-run double build, update both checkpoint files). Intended F6 detection semantics, but the re-anchor procedure should be documented so CI failure is read as "re-anchor", not "regression".
2. **Build-path `--verify` self-anchors** (freshly computed fingerprint); only `--verify-pack` uses the external anchor. A build can pass while drifting from the committed checkpoint. The committed test closes this for CI; the manual loop may want a `--expect-checkpoint PATH` convenience. Optional.
3. Recorded counts not independently executed (Bash denied); values are internally consistent with the file contents (5 new harness tests + updated budget tests explain 66→73; checkpoint fingerprint matches the claim).
4. Transport test env-isolation fix (`delenv`) from a prior round is untouched by this fix set.

## Recommended Next Step

Accept F1–F6 as closed. The next safe engineering action is small and optional: document the checkpoint re-anchor procedure (boundary 1) next to the checkpoint JSONs — a toolchain change requires re-running the double build and updating both checkpoint files. No code change strictly required; no clinical acceptance implied.

**Bounded questions for Codex:** (1) Should build-path `--verify` optionally compare against the committed checkpoint, or is `--verify-pack` the designated external-anchor path? (2) Is re-anchor documentation a follow-up here or implicit in the checkpoint schema (`recorded_at` + toolchain)? (3) Are the recorded 73/1033 counts final acceptance evidence, or does Codex want an independent execution before close-out?
