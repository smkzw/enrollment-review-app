# Codex Conference Review: enrollment-reading-view-integration-20260916

Date: 2026-09-16

## Verdict

Revise. CodeBuddy/codebuddy-cli/deepseek-v4.1-flash requested max, one round, exit 0, no fallback. Source-only independent review; not clinical acceptance.

## Boundary Compliance

Reviewer used read-only file tools. Bash unavailable; no model calls or clinical database writes. Owner alone edits product source.

## Participant Outputs Reviewed

Reviewed runs/conference/enrollment-reading-view-integration-20260916/evidence_single_object.md and terminal receipt. The report is evidence, not authority; all adopted defects were checked against current source.

## Conference Panel Review

V1 accepted: derived view bytes missing from artifact store blocked request persistence. Added distinct reading_view_image storage; versioned request receipt preserves original source identity, derived hash and actual bytes. V3 accepted: request storage failure was outside receipt try; moved within recorded path and classify pre-dispatch failure as configuration, avoiding endpoint retry/fallback. V2 accepted as remaining product gap: changing direction on completed coverage needs controlled successor semantics, not a fresh ambiguous root. Do not relax coverage guards without a persisted change reason. V4 coordinate naming concern retained; current image dimensions and inverse mapping are explicit but do not authenticate locations.

## Main-Venue Codex Review

Reject treating absence of direction metadata as a clinical missing-evidence state on every page. Not knowing orientation is not proof that clinical evidence is missing. Reject requiring users to rotate every page. Existing EXIF/PDF metadata application is retained; unmarked sideways scans need a general preprocessing solution. Independent reviewer suggestion of an extra large-model call on every page is only an option, not chosen architecture.

## Codex Independent Verification

Owner executed actual ArtifactStore round-trip in disposable temporary storage with synthetic PNG: original page-request/v1 retained; derived page-request/v2 resolves reading_view_image bytes and original source hash. Error classification preserves configuration failure. Relevant modules compile. No new test suite, product model call, clinical DB write or browser acceptance. API/service orientation propagation checks from prior work remain engineering-only evidence.

## Final Decision

Keep integration incomplete pending direction correction lineage and user-facing behavior. Research first-party lightweight orientation classification and actual deployed image preprocessing before adding a full VLM pass; no new dependency installed or model default changed. Goal active, claims_complete=false.
