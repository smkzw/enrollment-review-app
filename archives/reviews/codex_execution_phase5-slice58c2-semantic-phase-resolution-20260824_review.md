# Codex Execution Review: phase5-slice58c2-semantic-phase-resolution-20260824

## Verdict

ACCEPTED for Slice 5.8c-2 only. The system now separates structurally explicit
phase applicability from semantic ambiguity, resolves only the ambiguous units
through a source-grounded four-way contract, and refuses publication whenever
results are missing, unresolved, inconsistent with the selected phase, or no
longer match the frozen source package. This is not acceptance of the 1,433
D001 semantic decisions, the D001 II manual control matrix, or any subject
eligibility review.

## Worker Outputs

- `worker_01` implemented the four-way applicability contract and deterministic
  gate. Evidence excerpts must be verbatim spans from the cited frozen units;
  `UNRESOLVED` overrides require an existing unresolved source basis.
- `worker_02` implemented ambiguity-only Agent planning, strict JSON hydration,
  and a full-manifest context index. Three same-session repairs replaced global
  context copying with target-relevant retrieval while preserving same-table
  closure.
- `worker_03` integrated a non-mutating semantic resolution view with the full
  protocol publication gate. A same-session repair then bound every package to
  the exact frozen manifest identity and exact source-unit payload, not merely
  matching IDs.

## Manager Assessment

The selected live execution route was `codex-subagent/codex/gpt-5.6-luna:max`.
All three serial workers completed on the declared route without fallback.
Worker reports were treated as implementation evidence only; Codex reviewed the
combined source, sent bounded same-session repairs, and reran focused and full
protocol tests.

The first real D001 plan was rejected despite being structurally valid: it
copied nearly every explicit unit and broad keyword match into every package,
creating 235 packages with roughly 1.715 million prompt characters each and an
estimated 403 million characters overall. The accepted planner keeps one frozen
full-manifest index, then retrieves target-relevant headings, phase anchors,
cross-references, local neighbours, and complete table context. The final D001
probe produced 235 packages with 36/40/145 context units and
52,964/61,674/207,886 prompt characters at minimum/median/maximum. The maximum
remains below the workflow runner's 240,000-character input boundary.

Unknown applicability is never converted to shared applicability. Explicit
selected-phase, opposite-phase, and shared units remain deterministic context;
only truly ambiguous units are Agent-owned. A mixed table row with multiple
source members remains unresolved until a future member-level contract can
represent it without flattening the source logic.

## Boundary

This acceptance covers contracts, semantic package planning, source-grounded
hydration, the non-mutating resolution view, and publication blocking. It does
not claim that a live model has resolved the D001 units, that the complete
protocol controls are clinically correct, or that D001/MG subjects and browser
flows have been tested. The independent tester routes were not started.

## Hermes

Hermes was not used for transport or review. The live guard selected the native
Codex subAgent route declared above. Same-session repair prompts are preserved
under the workflow `followups/` directory; they are not additional roles. Native
session and runner evidence must identify the same provider, model, effort, and
session before this slice can pass workflow audit.

## Codex Independent Verification

- Focused post-integration regression: `100 passed`.
- Full protocol regression: `605 passed, 58 warnings` in 269.17 seconds. The
  eight LibreOffice aborts reported in an intermediate worker run did not recur
  in the parent rerun and are not retained as blockers.
- Real read-only D001 II probe: 1,689 manifest units, 1,433 ambiguous targets,
  235 packages, and 37 compact global anchors.
- D001 package context min/median/max: 36/40/145 units; prompt size
  min/median/max: 52,964/61,674/207,886 characters; total 17,337,795
  characters rather than the rejected roughly 403 million-character plan.
- D001 table 5 spans two packages but both contain all 13 table structure units,
  preventing batch boundaries from severing header, row, or table-title logic.
- Package/manifest identity, document hash, snapshot, selected phase, and every
  owned/context source unit are exact-match checked. Forged excerpts, altered
  spans, changed member/table context, stale hashes, and stale snapshots are
  rejected.
- D001 source remained unchanged: SHA-256
  `362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`,
  size 405,567 bytes, mtime_ns 1779871799537588300.
- `compileall` and `git diff --check` passed for the affected layers.

## Cleanup Decision

Archive runner-owned prompts, logs, reports, and manifest after execution audit
and review gate pass. Keep this Codex review, metrics, research note, and
accepted checkpoint as durable evidence. Continue with Slice 5.8d D001 II
manual control comparison and real semantic resolution before starting the
independent tester routes.
