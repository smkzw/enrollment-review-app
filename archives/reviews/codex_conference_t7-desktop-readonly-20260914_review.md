# Codex Conference Review: t7-desktop-readonly-20260914

Date: 2026-09-14

## Verdict

Revise. Independent source advisory completed; runtime and product acceptance remain open.

## Boundary Compliance

Actual grok/grok-build/grok-4.6 high, one fresh C03 pass, no fallback. Catalog/auth preflight succeeded; runner exit 0/end_turn and complete report received. Reviewer disclosed importing FastAPI to locate its installed source, outside the no-import/workspace-only assignment; do not claim full boundary compliance. No application, database, clinical-model or browser execution reported. Resident-session DeadFailed warning occurred at shutdown despite complete output; same-session resumability is not proven.

## Participant Outputs Reviewed

`runs/conference/t7-desktop-readonly-20260914/evidence_single_object.md`, SHA256 `0e9571f611bf213bd8f7616623a5399e9f7e05d4b96e1ecda66d8418278edb9c`; matching stdout receipt checked for actual identity, terminal reason and health result.

## Conference Panel Review

Accepted the material UI finding: a status banner plus backend rejection still invited action editing and navigation to unsupported pages. Accepted 403 instead of retry-like 503, and lazy normal-app import. Source-read database protection and frozen report/locator routes were judged coherent; no runtime acceptance follows from this.

## Main-Venue Codex Review

Implemented shell-level mode loading with explicit error/retry (no silent standard-mode assumption); browse navigation limited to reports/help and unsupported deep links return to reports. Report action editing/buttons are absent, while response history and source viewing remain. Backend rejects writes with 403 and the desktop factory selects browse without importing the standard factory first. This is report-and-source browsing, not a full offline clinical workbench. Existing service imports may still load model-related definitions/config; no claim of zero model dependencies. Standard runner shutdown's five-second join remains a separate final shutdown concern, not repaired by skipping disposal while a worker is alive.

## Codex Independent Verification

Owner inspected route/constructor/read consumers and changed definitions. Python compile/import, zsh syntax, production frontend compilation and build-file hashes passed. Corrected verification scope: root `tsc --noEmit` sees an empty files array and is insufficient; explicit `tsc -p tsconfig.app.json --noEmit` and `tsc -p tsconfig.node.json --noEmit` both pass. No staged tests or clinical database/model/browser invocation under the user's deferred-testing direction. Post-review edits have owner source/compiler verification, not a second independent runtime review.

## Final Decision

Retain changes as construction, not final delivery. Owner additionally replaced the five-second shutdown with awaiting the runner and added a stop check at the next committed step/wave boundary, reusing release_deferred without consuming attempts. Cancel/failure/complete handling stays ahead of stop return. This post-review change has source/compile checks only, not independent or runtime acceptance. Final checks must exercise double-click startup, failed startup, read-only WAL/compatible schema, frozen report/source/response reading, navigation, print and normal job shutdown on an isolated copy. T5 publication/binding and full-product acceptance remain open; claims_complete=false.
