# Codex Execution Review: phase5-package104-interim-analysis-governance-boundary-20260830

## Verdict

Accept. Package 104 is accepted only as a model-free source and research-governance boundary. It publishes no subject-level control point and does not establish full-protocol, subject-review, or Patient Profile completion.

## Worker Outputs

- `worker_01` independently reconciled the DOCX-derived structure, coverage manifest, frozen ownership, phase scopes, and Package 103-105 boundaries. It confirmed four owned sources and two read-only context sources.
- `worker_02` created the initial config, checklist, deterministic regression, and dry-run. Codex rejected its initial three-candidate design because the current candidate schema requires a subject review node and would force study governance into screening, baseline, or D1.
- `worker_03` exposed that schema-level conflict, phase-scope flattening risk, paraphrase bypass of exact marker probes, and possible inversion of the aggregate Week 12 trigger. Codex resolved these findings by keeping all six sources outside the candidate path and adding a real hydrated-gate regression keyed by source identity.
- `worker_04` independently reran the post-correction focused regression and dry-run. It verified exact source closure, prompt minimality, zero candidates/bindings, and no model or publication invocation.
- All four workers completed on `openai-codex/gpt-5.6-luna:max`; no fallback route was used.

## Manager Assessment

The Hermes workflow guard declared no execution manager for this packet. Codex retained source correction, clinical-semantic acceptance, deterministic verification, and final disposition ownership.

## Codex Independent Verification

- Frozen package: plan `papl-e17d498106b6f71f440ff2be`, Package 104 `pap-03856594c8db16e170f5a4db`, selected Phase II.
- Exact closure: four owned sources (`body.p1236`, `body.p1237#atom-0-15`, `body.p1237#atom-15-100`, `body.p1237#atom-160-208`) and two read-only sources (`body.p537`, `body.p1237#atom-100-160`). `body.p1210`, `body.p1223`, and the Week 12 atom remain unowned; `body.p1238` belongs to Package 105.
- The approximately 50% Phase II Week 12 trigger is an aggregate study-level timing condition. Independent statistical analysis, IDMC review and recommendation, sponsor continuation/dose decisions, and the independent interim SAP are research-governance concepts, not individual eligibility, screening, baseline, randomization, D1 pre-dose, visit, procedure, or action requirements.
- The current subject protocol-control candidate contract requires at least one subject review node. Creating a new study-governance candidate type is unnecessary for enrollment review, so the minimal correct boundary is zero candidates rather than weakening that contract.
- All six declared sources are forbidden candidate sources. A real hydrated-output regression now injects six paraphrased subject-level inversions that avoid the configured Chinese markers; each is rejected by `CONTROL_DUPLICATE_RETAINED` from source identity.
- Raw coverage preserves each source's `phase_scopes`, including `unknown`, `mixed`, and Phase II. Because no candidate is produced, mixed Phase II/III governance content cannot be flattened into a published Phase II subject control.
- Dry-run evidence contains only the six declared sources, empty `agent_candidates` on every QC row, no official rules, procedures, actions, visit bindings, or pre-enrollment sources, and `claims_complete=false`. The gate remains explicitly skipped because no hydrated Agent result was requested.
- Focused test: `11 passed, 5 warnings`. Adjacent Package 102-104 tests: `27 passed, 5 warnings`. `git diff --check` passed. Warnings are existing SWIG/PyMuPDF deprecations.
- SHA-256: config `ea82f92218c8368bd55f6cc75a77dc33bf64d8e7cde7aad2aa36163a9c02db8b`; checklist `5f8fbec09e1493552e98c469e9c295262a0f6522c9e942c4ee6a70d2be6df79a`; test `43d57953978e61c326202e8c3d150b34c6bbc1187c20c2e186e6dffec7623c18`.
- Residual downstream constraint: all `body.p1237` atoms share parent source span `body.p1237`; ownership and candidate checks must continue using structure-unit identity rather than source-span identity alone.

## Cleanup Decision

Archive runner-owned process files only after the review gate and formal execution audit pass. Preserve the accepted config, checklist, regression, dry-run evidence, review, metrics, and Package 104 checkpoint. Do not delete or rewrite frozen source artifacts.
