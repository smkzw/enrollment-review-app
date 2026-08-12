# Codex Review: enrollment_review_rearchitecture_20260812

Date: 2026-08-12
Independent reviewer: native Luna subagent `019ff50b-c91c-79e1-b49c-ea6d12b05056`

## Verdict

Discovery checkpoint accepted. The existing architecture requires revision before it can support the requested clinical evidence and multi-stage workflow. Large implementation is intentionally held pending user decisions.

## Boundary Check

- The independent reviewer was read-only and did not modify the workspace.
- Source protocols, raw subject documents, manual trackers, and existing clinical reports were not modified.
- Authorized writes were limited to launcher/health repair, one regression test, task records, discovery documentation, and browser audit screenshots.

## Codex Verification

- Verified port `8900` belonged to an unrelated local service and reproduced the old false-positive health behavior.
- Verified the enrollment service identity and live app at `http://127.0.0.1:8901`.
- Verified repository and desktop launcher identity, shell syntax, Python compile, and full unit tests.
- Reopened login, home, project list, subject list, subject report, and rule-management pages in a real browser.
- Inspected data models, stage/report state derivation, OCR cache, batch execution, processing locks, rule deconstruction, reviewer post-processing, permissions, audit log, and existing project footprints.

## Independent Review Assessment

- Accepted: classify the app as a local prototype/adapter rather than a production clinical workflow system.
- Accepted: retain safe upload/OCR adapters and compatibility projections; replace file/Markdown truth and request-owned workflow state.
- Accepted with user refinement: use three bounded semantic agents, deterministic gates, and structured action routing; Graph owns orchestration, not clinical truth. Do not build a multi-user approval chain for this local AI-led support tool.
- Corrected: the OCR cache is currently validated primarily by modification time, not by file size. The material concern is the absence of a source hash plus extraction-version fingerprint.
- Codex independently confirmed the main claims against the source and live runtime.

## Residual Risk

- Single-Mac/single-user deployment is confirmed, so SQLite/local background execution is now the leading direction; the exact Graph implementation remains provisional.
- No full migration, Patient Journey implementation, or clinical rerun has started.
- Existing projects remain on the legacy file model and retain its audit, concurrency, and top-level-verdict limitations until migration.
