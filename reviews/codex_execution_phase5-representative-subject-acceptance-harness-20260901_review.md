# Codex Execution Review: phase5-representative-subject-acceptance-harness-20260901

## Verdict

Accept after one same-session revision. The run-packet exporter is accepted as a deterministic acceptance aid, not as clinical acceptance and not as proof that a representative subject has passed.

## Worker Outputs

- Worker 01 mapped the existing V2 upload, evidence revision, Evidence Normalizer, publication, Patient Profile, and selective-vision entry points without changing files.
- Worker 02 implemented the source inventory/run-packet layer and tests. Its first pass was not accepted because unverified manifests, stale-authority rows, and incoherent locators could still appear verifiable.
- Worker 03 independently identified those defects plus explicit blocking regressions. Worker 02 resumed the same session and repaired the mandatory findings without changing application or clinical-source files.

## Boundary

Only the generic acceptance inventory/export tools and their tests were changed. Legacy projects, clinical source documents, old OCR/LLM outputs, the paused D001 control task, application runtime code, and frontend code were not modified by this execution packet. The output is a verification packet, never an enrollment or medical decision.

## Hermes

Hermes was not used as a transport or substitute. The live route declared `zcode/GLM-5.3:max` for all three workers and no manager; all workers completed on that route without fallback. The same Worker 02 session was resumed once for targeted remediation.

## Manager Assessment

The declared route has no separate manager. Codex performed disposal. The implementation reuses the existing V2 database contracts in read-only mode, records immutable source fingerprints and frozen authority, exports per-event source checks, and always states `clinical_acceptance.claimed=false`. It contains no study-specific clinical rule or subject identifier.

## Codex Independent Verification

- `135 passed, 1 deselected` across `tests/tools`, fact publication, Patient Profile, fact-normalization source/visual wiring, selective-vision observation, and independent-VLM deterministic tests.
- Targeted Python compilation and scoped `git diff --check` passed.
- Project-specific literal scan passed for the three changed implementation/test files.
- Desensitized live Coding Plan vision connectivity passed once: `1 passed, 27 deselected`; no credential or clinical response text was logged.
- Mandatory adversarial gaps now block: unverified/absent/out-of-root copies, authority-mismatched or stale Profile entities, absent entity links, incoherent locator excerpt/text hash, and normalization runs that do not match frozen authority.
- The D001 protocol-control job remains paused; no old OCR or LLM result was used as a new acceptance input.

## Cleanup Decision

Archive runner-owned process files after `review-gate` and `audit-execution` pass. Keep the accepted source tools/tests and a durable Trellis checkpoint. Do not clean or rewrite unrelated Phase 5 history.
