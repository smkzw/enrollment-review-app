Trellis SessionStart ✓

I'm a bounded conference worker (general_single_object) in plan mode. I'll read the assigned context, then audit the code independently, and return my report. All actions read-only.

The context files are templates. The real substance is the linked execution task `phase5-slice61ao-replay-harness-budget-contract-20260829` and the Phase 5.8d code. Let me locate them.

Bash is unavailable in this session; I'll rely on Glob/Grep/Read. Locating the Phase 5.8d task artifacts.

Found the linked execution task (slice61ao) and its test. Reading its context, plan, review, metrics, and test in parallel.

Now the Codex acceptance review and the harness code itself.

Reading the core harness implementation, CLI script, and harness tests.

Core harness read. Now the ingestion module (source artifact path-leakage check) and the runner budget implementation.

`storage_ref` is content-addressed and relative — good. Now the runner's budget loop implementation.

Runner loop verified: global budget, no_progress fingerprint `(raw_sha256, code, message[:2000])`, conservative stop. Now the snapshot/artifact models (path-leak + determinism), harness tests, and worker reports.

Snapshot models are path-free (relative content-addressed refs only). Now checking module-level imports of the deconstructor (transport-at-import risk), worker reports, and metrics evidence.

No transport/LLM imports at module level. Now checking for project-specific (D001/human-matrix/legacy span) dependencies in the harness chain, and reading worker reports.

No project-specific references in product code. Reading worker reports and looking for the D001 double-build evidence/checkpoint.

Worker reports align with the final code. Now checking `detect_required_action_kinds` for genericness, the transport test env-isolation fix, and the committed D001 checkpoint.

Transport test env isolation confirmed. Locating the D001 checkpoint and reading `detect_required_action_kinds`.

The D001 fingerprint exists only in review prose — no committed checkpoint/config. Checking `_error_class_codes` implementation and whether a replay config was committed.

Final targeted checks: the class-code regex and attempt model, plus confirming `__str__` of the wire validation error (fingerprint content).

One last set of verifications: `render_to_pdf` existence (cited in the PDF rejection message), any committed checkpoint, and `VersionedModel` behavior.

`render_to_pdf` exists — the PDF rejection message is accurate. Final check: any network-library imports in the chain modules.

All verification complete. I have a full picture. Writing my independent review report.

The full report follows. The runner-managed report path is not written; the report is returned here (and mirrored to the session plan file, the only writable file in this session).

# Conference Participant Output: phase5-slice61ap-replay-harness-budget-independent-review-20260829 - general_single_object

## Boundary Check

- All actions read-only (Glob/Grep/Read inside the runner CWD worktree). No edits, no model calls, no control publication, no production paths. Bash was permission-denied in this session (session restriction, not a hidden tool failure), so I could not re-run pytest; test-count claims are quoted as recorded evidence, not independently executed.
- Did not read other participants' outputs; the only worker reports read are the linked execution task's own provenance (`runs/execution/phase5-slice61ao-.../worker_01/02/03.md`), the Codex execution review, and metrics — the code-under-review's provenance, not peer review content.
- The D001 raw DOCX is committed in-repo, so reproducibility is fully auditable in principle.

## Independent Work Product

**1. Real product chain / model-free default — verified sound.** `build_protocol_replay_pack` composes only existing product functions (`register_source_artifact` → `extract_docx_structure` → `build_phase_applicability_graph` → `project_single_phase` → `build_full_protocol_coverage_manifest` → `stable_protocol_control_batch_id` → `build_protocol_control_agent_prompt`); no second implementation. Deconstructor imports are domain-only (no transport/LLM); `app/protocols/*` has zero httpx/requests/openai imports; `transport_instantiated: false` is recorded. PDF rejection is explicit, accurate (`render_to_pdf` exists at `app/protocols/rendering.py:106`), and Codex's acceptance list honestly marks PDF-to-structure as not delivered — the "DOCX-only must not be written as PDF-supported" constraint is satisfied.

**2. Hash/time pinning, path leakage, external fingerprint — verified.** `expected_protocol_sha256` mandatory + pre-write check; `pinned_created_at` required/tz-aware and propagates into `uploaded_at`/snapshot/`created_at`; config echo pops `protocol_path/out_dir/base_dir`; `storage_ref` is content-addressed and relative; models carry no absolute paths. The synthetic byte-reproducibility test builds into two different out_dirs and asserts equal fingerprints, so out-dir leakage fails CI. `replay_pack_fingerprint` hashes actual on-disk files including the summary — not self-reported hashes.

**3. Budget contract — verified.** Global budget (default 2), strict monotonic bound, no extra round for a class appearing after exhaustion, no-progress stop on identical fingerprint (raw sha + code + message) even with budget 10, deterministic same-sequence output, negative guards — all regression-locked in `test_slice61ao_repair_budget_contract.py`. I stress-checked fingerprint precision (same class/message on a different candidate): the raw-text SHA makes the fingerprint unique per distinct model output, and candidate identity is deterministically hydrated from that text — a false no-progress trigger requires identical text, which is genuine no-progress. Non-issue.

**4. Human-matrix / project-specific isolation — verified.** Grep-clean for D001/p803/p805/matrix/legacy span identities in the harness and chain; frozen targets are explicit optional config, not hidden dependencies; `detect_required_action_kinds` is project-neutral pattern matching. Worker_02's v8-anchor comparison shows the rebuilt prompt differs from the frozen D001 prompt only in system-derived identities.

**5. Codex post-revision changes confirmed present:** mandatory SHA + pinned timestamp, location-field stripping, fingerprint over actual files, budget kept at 2, transport-test ambient-key isolation (`delenv` at `test_protocol_control_agent_transport.py:356-357`), and the `sort_keys=False` fix for contract-critical dict ordering.

## Evidence And Assumptions

Evidence (read directly): `app/protocols/protocol_replay_harness.py`, `scripts/run_protocol_replay_harness.py`, `tests/v2/protocols/test_protocol_replay_harness.py` (13 tests), `tests/v2/protocols/test_slice61ao_repair_budget_contract.py` (5 tests), runner loop at `protocol_control_deconstructor.py:2402-2800`, `_error_class_codes` at `:1895`, `ProtocolControlAgentAttempt` at `:1861`, `app/protocols/ingestion.py`, `app/domain/contracts/protocol_ingestion.py`, execution context/plan/review/metrics, worker_02/03.

Recorded (not independently executed): 66 focused tests passed; protocol suite 1026 passed; D001 double build byte-reproducible with fingerprint `993594302ea9dd7c1037c28afc60e1fc228133e47d6e71a2e9766a961a7d1a5c`; stable identities (batch `pcb-b29b96bc…`, manifest `su-8f87873…`, snapshot `snp-e3e8bef…`).

Assumptions: `source_ref` namespace is stable for a fixed doc hash + parser version (parser_version recorded in snapshot); extraction guarantees unique source_ref per unit (see F4).

## Risks, Gaps, And Verification Needs

**F1 (highest impact): no durable external checkpoint.** The D001 packs lived in `/tmp`; the `9935…` fingerprint exists only in review prose; no replay config or checkpoint.json is committed although the DOCX is in-repo. Routine `--verify` runs without `--expected-fingerprint`, making it self-consistency-only. The "整包外部指纹 + 双运行可重现性" evidence is ephemeral. **Fix:** commit `artifacts/phase5-slice61ao-.../replay-config.json` + `checkpoint.json` and a rebuild-and-compare script/test.

**F2: self-verify doesn't cross-validate summary identity fields** (batch_id/manifest_id/snapshot_id/owned refs vs. actual JSON contents; `replay-input.json` never revalidated). Summary-only tamper is caught only via expected_fingerprint (the test proves it). **Fix:** cheap identity cross-checks + replay-input validation; make `--expected-fingerprint` encouraged/required on verify.

**F3: `_error_class_codes` text regex** `([A-Z][A-Z0-9_]{2,}):` over `str(error)` — future gate messages with "NOTE:"-style tokens would be misreported as classes, corrupting the class-by-class audit trail. Latent (current messages scanned clean). **Fix:** carry structured codes on the combined error.

**F4: `_resolve_units` silently collapses manifest-internal duplicate source_refs** (dict by_ref) — owned scope under-resolves without build-time error. **Fix:** assert `len(by_ref) == len(manifest.units)`.

**F5: import-time transport isolation isn't regression-guarded** — the import-spy test snapshots sys.modules after the chain is already imported. Manual inspection is clean today. **Fix:** cold-import check.

**F6: toolchain versions not recorded** — pydantic/Python upgrades could flip bytes; record versions in replay-input/summary.

**F7 (minor):** CLI resolves relative paths against CWD, not the config directory; build failure deletes a pre-existing empty out_dir (both documented).

Verification needs: re-run the two focused test files + full protocol suite; re-run the D001 double build against the in-repo DOCX and commit the fingerprint as a checkpoint (F1).

## Recommended Next Step

Implement F1 (committed D001 checkpoint: config + expected fingerprint + rebuild-and-compare) and F2 (summary↔content identity cross-checks + replay-input revalidation) as minimum hardening — small, read-only-safe, and they close the gap between the *claimed* external fingerprint / dual-run reproducibility and the *verifiable committed* state. F3-F6 can ride along or be logged as follow-ups. Engineering-infrastructure only; no clinical acceptance impact.

**Bounded questions for Codex:** (1) Is the D001 pack + `9935…` fingerprint meant to be a committed auditable checkpoint, and if so CI test or documented manual script? (2) Is the trust anchor the external fingerprint only, or should self-verify be closed (identity cross-checks) with a warning when no expected_fingerprint is given? (3) May `error_classes` switch from text-regex to structured codes, or is message-text the normative source? (4) Is import-time transport isolation a requirement of the model-free default, or is build-time isolation the intended contract?

The report is complete and returned above (ExitPlanMode was denied, which is fine — this was a read-only review with no implementation to approve; the deliverable is the report itself, mirrored to the plan file for the runner).
