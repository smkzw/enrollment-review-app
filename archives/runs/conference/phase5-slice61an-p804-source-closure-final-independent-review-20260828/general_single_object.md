Trellis SessionStart context loaded. Beginning the independent review pass — reading the initial read set first.

The two packet files are mostly templates with TODOs — the real substance is the linked execution task and the Trellis task artifacts. Let me locate them and the underlying code.

Bash is unavailable — proceeding with read-only file tools (Glob/Grep/Read).

The slice chain is now clear: 61ab → 61af → 61ag → 61ai → 61ak → 61al (the repair execution under review) → 61am (linked route verification) → 61an (this conference). Reading the execution contexts and reviews for the two key slices.

The review trail gives me a strong picture. Now I need to verify the actual shared implementation. Locating the protocol modules and test files.

Reading the core bounded restore/validate logic and the runner loop — the heart of the contract under review.

Now reading the runner loop to see how the closure parameters are derived and passed.

I now have the full restore/validate/runner picture. Next: verify test coverage of the real runner, check for D001-specific hardcoding, and inspect the execution auditor.

No D001/p804-specific hardcoding found in shared code — only generic comments. Now reading the focused contract test file to assess runner coverage.

Comprehensive contract tests confirmed. Now checking the gate-side: where `control_to_candidate` is built and how `replay_validation_error` is invoked in the real flow.

`control_to_candidate` and `replay_validation_error` appear to have no production callers outside the module itself. Verifying call sites of `publication_repair_error` and the runner.

Critical question: is the runner wired into any production flow? Searching broader.

Now examining the gate's control-scope path — how `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` issues are raised at control level and what entity_id they carry.

Reading the publication gate section where the scope-split check is invoked at both candidate and control scope.

Verifying whether any test drives the runner with the real transport factory, and locating the immutable v8 evidence.

Reading the v8 rejection checkpoint and the replay-accepted checkpoint to verify the clinical evidence boundary.

Now verifying the execution auditor's route anchoring and the metrics evidence for both execution slices.

The auditor code itself is outside my work boundary — I'll verify its claims via artifacts inside the workspace. Searching for the execution-audit records.

The 61am worker transcripts confirm an important gap: the 61al "real v8 offline restore" had no persistent artifact — worker_03 had to re-run it. Checking the 61al route records and the v8 evidence artifacts.

Reading the immutable v8 evidence artifacts — the offline recovery and parent clinical reassessment.

The immutable v8 evidence is solid and consistent. Now checking the wire-level source validation to assess the closure-trust model for cross-unit span absorption.

The v8 live replay did use the real transport. Finding the replay script that drove it, to confirm the runner's live-path usage.

Let me verify the repair guidance text and check the phase5 PRD acceptance framing briefly.

Checking the phase5 design doc's source-closure contract definition against the implementation.

One final check to make the production-wiring claim airtight — searching the whole repo (excluding tests/vendor) for runner usage.

I have completed my independent audit. Writing the final report.

---

# Conference Participant Output: phase5-slice61an-p804-source-closure-final-independent-review-20260828 - general_single_object

## Boundary Check

- Role: `general_single_object` (codebuddy-cli / deepseek-v4-flash / effort max). Session route is consistent with the packet CST chain; the excluded node `codebuddy-cli/glm-5.3` (used by linked execution 61am) is correctly not me.
- **Read-only**: no files modified, no clinical artifacts touched, no model replay run, no control point published. All evidence gathered via Read/Glob/Grep inside the worktree CWD.
- **Tool limitation disclosed**: Bash execution is denied in this non-interactive session. Consequences: (a) I could not re-run the focused/full test suites; (b) I could not recompute SHA-256 hashes of the immutable artifacts or code files; (c) I could not run a deterministic offline restore myself. All pass-count and hash claims below are therefore corroborated by artifact content and review text, not re-executed by me. This is an evidence gap, not a hidden failure.
- Boundary note: the execution auditor (`hermes_workflow_guard.py`) lives outside the CWD; I did not read it. The route-anchoring claim is assessed from in-workspace artifacts only.

## Independent Work Product

I traced the complete chain: gate check → `publication_repair_error`/`combined_repair_error` → `ProtocolControlAgentRunner.run()` → `_restore_bounded_wire_repair`/`_validate_bounded_output_repair` → re-hydration → re-validation, plus the test file `test_slice61ab_candidate_repartition_contract.py`, the v8 immutable evidence (`replay-summary.json`, `parent-clinical-reassessment.json`, checkpoint `CHECKPOINT_20260828_V8_SCOPE_SPLIT_REJECTED.md`), the 61al/61am reviews, metrics, and archived worker transcripts.

### 1. Source-closure ↔ atom-span mutual exclusion — verified, correct

`publication_repair_error` (`app/protocols/protocol_control_repair_errors.py:43`) and `combined_repair_error` (`:126`) both zero out `obligation_source_span_ids` whenever any issue authorizes repartition or closure rewrite. In `_restore_bounded_wire_repair`, the atom branch (`protocol_control_deconstructor.py:2004`) hard-rejects `closure_rewrite or not mutable_candidate_source_keys`, and the closure branch (`:2121`) hard-requires a non-empty union. The mutual exclusion is structural, not heuristic. The 61am normalization (mixed report carries no atom spans from another issue) is covered by `test_scope_split_drops_atom_spans_from_other_publication_issues` and `test_combined_source_closure_repair_drops_other_atom_spans`. No D001/p804-specific code found (grep across `app/` matches only generic comments).

### 2. Control-level closure seed recovery — implemented, tested, but not production-reachable

`publication_repair_error:66-78` resolves a candidate id from `entity_id` via `candidate_by_id` → `control_to_candidate`, then seeds `structure_unit_ids` from the candidate's frozen units. Tested by `test_control_scope_split_resolves_candidate_for_source_closure`. The gate emits control-level issues with `entity_id = protocol_control_id` and empty `candidate_ids` (`protocol_control_gate.py:1955-1967`, invoked at `:4003-4007`), and controls carry `originating_candidate_id` (`:3996`), so a real map is derivable.

**Critical caveat**: `replay_validation_error`/`publication_repair_error`/`control_to_candidate` have **no production caller** (grep across `app/` finds only the module itself and tests). The whole repair-error→runner pipeline is exercised only from tests and from Codex's inline replay scripts. When a real repair eventually runs, the map must be built from `originating_candidate_id`; that wiring does not exist yet.

### 3. Out-of-closure freezing — correct, with one transparency nuance

Restore (`:2127-2162`): previous candidates whose key is outside the closure keys are re-emitted verbatim; current candidates disjoint from the union are silently replaced by their previous versions; crossing candidates and union drift raise `REPAIR_SCOPE_ESCAPE`. A model-invented out-of-closure candidate is dropped-and-restored without an error — acceptable because the attempt issue list records "已由系统原样保留定向修订范围外的上一轮内容", and `_validate_bounded_output_repair` re-checks frozen candidates at the hydrated level. Tests cover both sibling rewrite and multiple frozen different-source siblings.

### 4. Source-set conservation — enforced, fails closed

`current_union != mutable_candidate_source_union` or any crossing candidate → `REPAIR_SCOPE_ESCAPE` with the union as `structure_unit_ids` (`:2155-2161`). Dropping/adding source units inside the closure is rejected; splitting/merging candidate counts is allowed by design (that is the purpose). Covered by `test_source_closure_rewrite_rejects_source_loss` and `..._rejects_cross_source_absorption`. Atomic source fidelity inside the closure is additionally bounded by `_validate_exact_atom_sources` (`:1252`): atom spans must belong to the candidate's own source units and excerpts must be contiguous original text.

### 5. "Tests cover the real runner" — true at class level, false for production wiring

- `test_scope_split_runner_uses_source_closure_not_atom_repair`, `test_synthetic_runner_*`, and `test_slice58c_control_deconstructor` drive the actual `ProtocolControlAgentRunner` loop (parse → restore → hydrate → validate → repair prompt → continue_session) with `_FakeTransport`. This is genuine runner-class coverage, not direct-function coverage — worker_02's claim is accurate at this level.
- However, `ProtocolControlAgentRunner` has **no caller anywhere in `app/` or `scripts/`** except its own module and tests. The v8 live replay ran the real runner with the real MTPLX transport (`replay-summary.json`: `mode: live_mtplx_runner`, `transport_identity`), driven by a **Codex-parent inline script that is not committed**. No production service step invokes the runner today.
- Implication: the contract governs a repair loop that is currently reachable only by tests and by Codex's one-off scripts. This must not be read as production-path coverage.

### 6. Execution-package audit anchoring — documented and corroborated, code unverifiable by me

The 61am review states the auditor was changed from comparing historical packets against the current route manifest to reading each packet's immutable worker route from its execution context. Corroborating evidence in-workspace: metrics for 61al (cursor-cli/auto) and 61am (codebuddy-cli/glm-5.3) match each packet's declared `Effective worker chain`; archived dispatch JSON records the same provider/model per round with `explicit_route: false` (consistent with guard-resolved routes, not user routes). The auditor code itself is outside my boundary — Codex should confirm the change and attach an audit run to the archive.

### 7. Engineering usability ≠ clinical pass — confirmed, boundaries held

- v8 immutable evidence: `parent_clinical_acceptance: "rejected"`, `gate_accepted: false`, `published: false`, 5 attempts ending `schema_invalid`, `claims_complete: false` (`replay-summary.json`, `parent-clinical-reassessment.json`).
- After offline restore with the accepted contract: p805 restored to A4 (three trigger branches + shared 28-day validity + conditional no-recheck accepted); p804 still raises `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` (HBsAb/HBeAg/HBeAb remain unconditional screening siblings). The `_repair_problem_guidance` for `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` is generic, carries the correct clinical semantics (merge validity condition + no-recheck consequence into the same candidate), and the leak test pins p804/p805/HBsAb etc. as forbidden terms.
- All reviews (61al/61am/61ak) and the checkpoint explicitly separate "contract accepted" from "clinical content rejected". This boundary is maintained; I found no artifact that blurs it.

### 8. Prerequisites for one new immutable replay — mostly in place, three conditions missing

In place: tested generic contract (focused suite with merge/split/absorption/loss/freeze/shuffle/empty-closure/mixed-report cases), runner-class regression, immutable v8 evidence with recorded hashes, generic leak-free guidance. Missing before Codex decides a replay: (a) a **committed reproducible replay harness** (the v8 one was inline/uncommitted — see F2/F4); (b) explicit confirmation of the closure definition (F1); (c) an explicit `max_schema_repairs` budget sufficient for closure rewrite + any residual atom issue (F3).

### Highest-impact findings

**F1 — Closure-widening risk (primary objection).** The runner's closure expansion (`protocol_control_deconstructor.py:2600-2625`) grows from the seed candidate's source key by **transitive key intersection over all baseline candidates in the batch**, not by the issue's own `structure_unit_ids`. For real v8 this is harmless (p804/p805 are disjoint units), but if any baseline candidate spans two units (e.g., a p804+p805 combined candidate, exactly the shape seen in `_mixed_decision_stage_candidate` and the real p803-p805 group), the closure silently unfreezes the "must-freeze" other source: the model's rewrite of that pulled-in candidate would be **accepted**, not restored. The current `test_source_closure_rewrite_restores_different_source_candidates` only tests fully disjoint keys. Remediation options: (i) restrict closure candidates to those whose key intersects the issue's own `structure_unit_ids` and fail closed to 需要核对 if expansion reaches beyond; (ii) at minimum, add a focused test with a candidate spanning closure-unit + frozen-unit to pin the boundary, and document the definition as transitive key-intersection in the checkpoint. **Decision point for Codex: is transitive key-intersection the intended "同源来源闭包" definition, or must closure be bounded by the issue's structure units?**

**F2 — Runner production wiring absent + no committed replay harness.** The contract and its tests are real, but nothing in `app/` or `scripts/` invokes `ProtocolControlAgentRunner`; the only live-run evidence is the immutable v8 artifact set driven by an uncommitted inline script. For an auditable v9-style replay, the harness (batch assembly, transport config, validator wiring) should be committed before the run.

**F3 — Repair-budget serialization with mixed reports.** Dropping atom spans from a mixed report (by design) forces sequential scopes: one closure round, then one atom round per remaining issue. With the default `max_schema_repairs=2`, a closure + 2-atom report exhausts the budget and lands in 需要核对 even though each fix is mechanical. The v8 replay used ≥4 repair rounds (5 attempts), so any new replay must set the budget explicitly. Conservative fail-closed, but the default should be revisited or made scope-aware.

**F4 — 61al offline-restore result was not a persistent artifact.** The 61am worker_03 transcript explicitly records that it could not find the 61al offline A4/A5 restore procedure and re-derived it from current code. The conclusion is independently corroborated (two independent derivations agree), but the procedure itself should be committed as a script or recorded as an exact command so future audits are deterministic.

**F5 (minor, fail-closed by design).** Atom-level span repair on same-source siblings always raises `REPAIR_SCOPE_ESCAPE` ("候选对应关系不唯一"); the `candidate_indexes` disambiguation computed by the runner is ignored by the atom branch. Safe (no wrong-target repair), but should be documented as a limitation.

## Evidence And Assumptions

| Claim | Evidence | Status |
|---|---|---|
| Mutual exclusion closure/atom | `protocol_control_repair_errors.py:43-160`, deconstructor `:2004-2162`; 3 tests | Verified by reading |
| Control-seed recovery | `repair_errors.py:66-78`; `test_control_scope_split_resolves_candidate_for_source_closure` | Verified; no production caller (assumption: wiring deferred) |
| Source-set conservation | restore `:2155-2161`; 2 tests | Verified |
| Out-of-closure freeze | restore `:2127-2162`; 4 tests | Verified |
| Runner-class coverage | 4+ runner tests with `_FakeTransport` | Verified |
| No production runner caller | Grep `ProtocolControlAgentRunner` in `app/`+`scripts/` → only definition + tests | Verified (evidence, not assumption) |
| v8 immutable evidence | `replay-summary.json`, `parent-clinical-reassessment.json` content | Verified by reading; hashes **not** recomputed (no Bash) |
| p804/p805 boundary | Checkpoint V8_SCOPE_SPLIT_REJECTED; parent reassessment findings | Verified |
| Route records | 61al/61am metrics + archived dispatch JSON | Verified; auditor code change itself unverifiable (outside CWD) |
| 45 focused / 1005 full pass | Codex 61am review | **Unverified by me** — requires re-run |
| Code hashes (`c5453a8d…`, `3f5e6d00…`, `ee41328a…`) | Codex 61am review | **Unverified by me** — requires re-hash |

Assumptions: (1) the current worktree state is the same code the 61am review verified (no commit between review and now — 726 dirty paths are consistent with in-progress slice work); (2) `control_to_candidate` will be built from `originating_candidate_id` when the pipeline is wired; (3) `explicit_route: false` is the expected marker for guard-resolved routes.

## Risks, Gaps, And Verification Needs

1. **Run the suites**: focused contract suite (expect 45) and full `tests/v2/protocols` (expect 1005, 58 warnings) against the current worktree; record actual numbers.
2. **Re-hash**: the 5 v8 evidence artifacts and the 3 code/test files against the 61am review hashes.
3. **Confirm the auditor change** and attach one `audit-execution` output (61al + 61am packets) to the archive.
4. **Commit the offline-restore procedure** (61al/61am style) so the "p805 restored / p804 still split" claim is reproducible by anyone.
5. **Decide F1** (closure definition) and **F3** (repair budget) before authorizing a replay.
6. Residual risk if not addressed: a future closure rewrite on a group with multi-unit candidates could accept rewrites of a source Codex intended to freeze — silent, gate-compliant, clinically wrong.

## Recommended Next Step

1. I **confirm** the 61al/61am contract as a generic engineering contract with correct invariants, and I **confirm** that v8 p804 remains clinically rejected — the engineering/clinical boundary holds everywhere I looked. The evidence supports Codex deciding **whether** to run one new immutable replay; it does not by itself authorize one, and I have no objection to the replay proceeding once F1–F4 are closed.
2. Before the replay decision: run the two suites, re-hash the artifacts, commit the replay harness, and add the F1 multi-unit closure test. Set `max_schema_repairs` to ≥4 (or scope-aware) for the replay run.
3. My bounded questions for Codex:
   - Q1 (blocks replay): Is "同源来源闭包" defined as transitive candidate-source-key intersection, or must the closure be bounded by the issue's `structure_unit_ids`? If transitive, do you accept that a batch candidate spanning p804+p805 would unfreeze p805?
   - Q2: Should I treat the absent production caller of `ProtocolControlAgentRunner` as a deliberate deferred wiring step (this slice), or is a production integration test in scope for a future slice?
   - Q3: For the new replay's batch, will the p804 group be run as `owned={body.p803,p804,p805}` again, and is the acceptable outcome "one p804 candidate carrying screening obligations + shared 28-day validity + conditional no-recheck", with p805 candidates byte-identical to A4?
   - Q4: Can the runner budget be made scope-aware (repair rounds = distinct scope classes) instead of a fixed count, to avoid spurious 需要核对 on multi-issue reports?
4. Safe provisional path if any question blocks: keep v8 immutable and rejected; do not publish; add the F1 test and the committed harness; re-verify suites; then return to Codex for the replay go/no-go.
