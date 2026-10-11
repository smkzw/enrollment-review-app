# Codex Conference Review: phase5-clinical-facts-profile-planning

Date: 2026-08-22

## Verdict

PASS WITH PLANNING REVISIONS. Both independent passes were substantive; the Phase 5 PRD and new design/implementation plan were revised before approval is requested.

## Boundary Compliance

- Read-only participants stayed inside the isolated Phase 5 worktree and did not inspect raw external clinical material or edit files.
- Neither participant claimed final clinical, browser, or visual acceptance.
- Conference and future tester roles remain separate. The user-selected local Qwen tester replaces ox-alpha only in Phase 5 test acceptance, not in this conference.
- The Hermes workflow guard and conference runner were used only for bounded routing, session evidence, and report persistence; Codex retained the final planning decision.

## Participant Outputs Reviewed

- `general_pi_qwen38`: actual route `pi/cms-smk/deepseek-v4-flash` max, one pass, no fallback.
- `general_grok46`: actual route `grok/grok-build/grok-4.6` high, one pass, no fallback.
- Both reports were read in full and checked against current contracts, storage identities, Phase 4 locator/processing runtime, and Profile frontend stubs.

## Conference Panel Review

Both participants independently found the same blocking class: Phase 2 fact placeholders point to the old snapshot authority while Phase 4's active truth is the paired v2 snapshot and complete processing revision. They also agreed that candidate and published types must be separated, Phase 4 authenticated locator ids must remain the location authority, silence cannot produce negative facts, conflicts cannot auto-resolve, and Phase 5 must not create ReviewRun/ActionRequest/eligibility status.

Useful differences were reconciled as follows:

- Use new v2 write tables rather than repointing legacy FKs.
- Reuse Phase 4 Job/lease/checkpoint/idempotency, not a new graph framework.
- Default Normalizer slice is one logical document; continuous page groups are allowed only for oversized documents with document/page coverage closure.
- Profile first-screen highlights are server-projected. Source-reported/reference-range abnormality may be shown; protocol-threshold eligibility interpretation waits for Phase 6.
- Candidate confidence remains audit-only and cannot govern publication or visibility.

## Main-Venue Codex Review

Codex re-opened the relevant contracts, storage schema, implementation-plan Phase 5 section, and frontend runtime boundary. The highest-risk mismatch is confirmed in current source: existing fact tables/contracts cannot express the complete processing revision, while the current Profile is fixture/stub only. The global Phase 5 plan line that prematurely linked EvidenceExpectation to Action was corrected to retain a structured future-action gap without creating ActionRequest.

No product code, migration, live model normalization, browser UAT, or clinical-case acceptance was performed because Trellis status remains `planning` and user implementation approval is still required.

## Codex Independent Verification

- Re-opened the approved design and phased plan, current Phase 5 contracts, Phase 2 placeholder storage, Phase 4 active evidence/locator/job boundaries, and Profile frontend repository path.
- Confirmed conference report session/provider/model identity from runner JSON rather than role filenames.
- Ran prompt preflight, conference packet validation, review/metrics gate, Trellis context validation, JSON/JSONL parsing, and `git diff --check`.
- Browser, PDF/image, live Normalizer, and real clinical-case checks are intentionally not run during planning; they are explicit implementation exit gates.

## Final Decision

Accept the revised Phase 5 planning package for user review. Do not run `task.py start` or modify product code until the user explicitly approves Phase 5 implementation in a subsequent message.
