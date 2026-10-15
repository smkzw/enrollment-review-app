I'll start with the assigned conference context and plan, then independently audit conflict-source successors, preservation, consumers, and replay interactions.Context and plan are loaded. Next I’ll inspect the design, storage/service code, consumers, and tests for unresolved-conflict successor behavior.The successor modules exist; I’ll read the design section, storage/service implementations, and the listed consumers next.Core successor path is in view. I’ll trace consumers, validation, and tests for head selection, member preservation, and correction/replay.I’ve got the successor write path. Next I’ll inspect contracts, head selection, correction exclusion, and the publication tests for gaps.# Conference Output: r06-conflict-source-review-20260913 - evidence_single_object

## Output

Read-only review. No source edits, no test run, no clinical DB/originals, no visual/browser acceptance. Codex remains final authority.

Read (assigned + needed consumers): `context/r06-conflict-source-review-20260913_conference_context.md`, `plans/codex_main_venue_r06-conflict-source-review-20260913.md`, `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.5, `docs/PROJECT_CONTEXT.md` (R06 status only), `app/storage/active_conflicts.py`, `app/storage/source_conflict_successors.py`, `app/services/source_conflict_successors.py`, `app/storage/source_reference_successors.py`, `app/services/source_reference_successors.py`, `app/domain/contracts/facts.py` (`ClinicalConflictGroupV2`), `app/storage/fact_repositories.py` (`ClinicalConflictGroupV2Repository.create/_load_members/list_for_authority`), `app/services/fact_publication_service.py` (publish, replay, `_publish_conflicts`, inherited facts), `app/services/patient_profile_service.py` (`_published_conflicts`, `_validate_referential_closure`), `app/services/eligibility_review_projection.py` (`_phase3_conflict_groups`), `app/services/fact_correction_service.py` (active conflict filter, `_recompute_conflict_groups`, `_append_successor_conflict`), `app/storage/fact_correction_commit_repository.py` (`superseded_conflict_ids`), `app/storage/active_facts.py`, `app/domain/gates/fact_batch_orchestration.py` (`detect_semantic_conflicts`), `app/workflow/runner.py` (session.begin ownership), `app/services/fact_normalization_executor.py` (publish error → StepFailure), `tests/v2/services/test_fact_publication_service.py` (`test_source_append_with_unreconciled_conflict_rolls_back`), `tests/v2/services/test_eligibility_review_projection.py` (mixed/dead conflict tests), `tests/v2/services/test_fact_correction_job.py` (event/exposure correction cascade). Extra reads were required because current-head consumers and correction/replay are in the assigned scope; nothing outside the worktree was written.

---

### Evidence

**E1. Source-only conflict successor is an explicit new row, not an in-place resolve.**  
`ClinicalConflictGroupV2` now has `source_revision_of` and `revision`; `resolution_revision` must stay 0 (`facts.py` 572–616). `append_source_conflict_successors` copies the current head, remaps one member-id list, unions locators from members, hashes a new `conflict_group_id`, sets `source_revision_of=prior`, `revision=prior+1`, same `gate_id`/`resolution_revision` (`source_conflict_successors.py` service 8–34). Publication calls it only after fact inheritance and event/exposure source successors (`fact_publication_service.py` 305–335).

**E2. Head selection folds source parents first, then excludes correction-superseded IDs.**  
`source_conflict_heads` rejects duplicate IDs, missing parent, second child of the same parent, cross-authority, `member_kind`/`gate_id`/`resolution_revision` mismatch, and `revision != parent+1` (`active_conflicts.py` 6–29). `current_conflict_heads` then drops IDs in `FactCorrectionCommitRepository.superseded_conflict_ids` after folding, with an explicit “removal cannot revive an ancestor” comment (32–42). Profile (`patient_profile_service.py` 368–372), eligibility (`eligibility_review_projection.py` 287–288), correction recompute (1498–1499), and source-append (service 16) all call this function.

**E3. Storage validation freezes clinical conflict payload and requires 1:1 member source growth.**  
`validate_conflict_successor` dump-compares everything except id/parent/revision/run/created_at/member lists/locators; rejects same `run_id`, non-head parent, mixed member kinds, length change, duplicate new IDs, and no-op `old_ids == new_ids` (`storage/source_conflict_successors.py` 14–34). Facts go through `validate_source_fact_references` (direct `inherited_from_fact_id` only). Events/exposures allow identity-same members or a direct `source_revision_of` child with frozen clinical dump except id/parent/run/revision/created_at/`fact_ids`; superseded entity IDs are rejected (35–60). Locator set must equal the member-union (61–63). `create()` then re-checks member authority, that the **prior** gate candidate still belongs to successor members, and locator closure (`fact_repositories.py` 2019–2052). Origin run for that gate is `prior.gate_id`’s run, not the new run (storage 64).

**E4. Publication fail-closes unclosed conflicts in the caller-owned transaction.**  
Service docstring: this service does not commit/rollback (`fact_publication_service.py` 1–6). JobRunner uses `session.begin()` (`runner.py` 147+). Nested savepoint is only in the unit test’s missing-successor branch (`test_fact_publication_service.py` 1288–1300). If append is patched to return `[]`, Profile closure raises and `FactPublicationError` is thrown; first-run facts and the original conflict remain. Replay of the same run returns persisted `run_id` conflicts and skips append (`fact_publication_service.py` 348–388; test 1281).

**E5. The only source-append conflict test is a one-sided fact conflict, one extra run.**  
`test_source_append_with_unreconciled_conflict_rolls_back` (1209–1300): run1 publishes a two-fact conflict; run2 inherits one side; asserts one successor, `resolution_revision==0`, `revision==2`, member count 2, locator superset, current head = successor, old row unchanged, several invalid `create()` shapes, in-memory fork, same-run replay, Profile `succeeded`. It does **not** assert which `fact_ids` were kept, `gate_id` frozen, third run, event/exposure conflicts, correction interaction, or two-sided re-extraction.

**E6. Eligibility still remaps stored members by `stable_identity` after using `current_conflict_heads`.**  
`_phase3_conflict_groups` keeps only `member_kind=="fact"`, then if `fact_ids` are not all current Profile facts, replaces each ID with `head_of_fact` (same identity’s current head). If the remapped set has fewer than two current IDs, the group is dropped; otherwise the **stored** group is kept but evaluated with remapped IDs (`eligibility_review_projection.py` 304–356). Tests `test_projection_keeps_mixed_revision_conflict_on_head_members` and `test_projection_skips_fully_superseded_conflict_groups` (409–469) construct conflicts pointing at superseded revisions **without** a conflict successor, and treat identity remap as the desired behavior. The “skip fully superseded” test still allows `decision in {inclusion_met, inclusion_not_met, conflict}`.

**E7. Profile and correction do not remap those members.**  
Profile: hanging conflict members → `PatientProfileProjectionError`, “绝不静默并入任意历史实体，也不改写任何 ID” (`patient_profile_service.py` 286–324). Correction’s “current projection” set silently omits a current head whose members are not ⊆ current entity heads (`fact_correction_service.py` 252–264). Correction recompute remaps via `_follow_entity_id` (correction edges + overlay), may collapse IDs with a set, and if signatures no longer differ, supersedes with `successor_id=None` (1529–1551).

**E8. Correction conflict “successors” are a second, incompatible type.**  
`_append_successor_conflict` creates a **new root**: no `source_revision_of`, `revision` defaults to 1, `gate_id` taken from `min(member_id, gate_id)` and is asserted to change in event/exposure cascade tests (`fact_correction_service.py` 1556–1603; `test_fact_correction_job.py` 1240–1241). Lineage to the old group is only `conflict_outcomes.superseded_conflict_group_id`. `source_conflict_heads` will treat that row as a root. If a future change set `source_revision_of` while keeping the new gate, folding would raise `gate_id` mismatch for the **whole authority**.

**E9. Same-run `_publish_conflicts` still inserts new roots from this run’s candidates only.**  
`detect_semantic_conflicts` keys this run’s candidates (`fact_batch_orchestration.py` 366–399). `_publish_conflicts` writes a revision-1 group with no parent (`fact_publication_service.py` 666–728) **before** `append_source_conflict_successors`. Append remaps existing heads; it does not suppress or merge a newly inserted same-member root.

**E10. Member remap in append is a last-wins dict; skip is list equality after `sorted()`.**  
`replacements` maps `inherited_from_fact_id` / event-exposure `source_revision_of` → new id (service 9–13). Unmapped members keep the old id. `validate_source_fact_references` rejects `current_ids == prior_ids` as lists, not as sets (`source_reference_successors.py` 61–62). Event/exposure validation has no post-loop `unmatched` assertion; length + unique + per-item parent removal imply emptiness if the loop succeeds.

**E11. PROJECT_CONTEXT overclaims consumer unification.**  
It states Profile, eligibility, and correction share current-conflict selection, that a 193-test run is not closure, and that third-revision / event-exposure conflict verification is unfinished. Head **selection** is shared (`current_conflict_heads`). Member **interpretation** is not (E6–E7).

---

### Inference

**I1. Highest-impact defect: implicit same-identity replacement remains a live eligibility proof, which this revision was supposed to retire.**  
After a successful source append, Profile and eligibility agree because successor `fact_ids` already are current heads (live path in E6). The forbidden path is the one the eligibility tests still encode: a current head whose stored members are old revisions. Publication now fail-closes that state; Profile fail-closes it; eligibility remaps and may keep or drop the conflict without a successor row. That is not “generic source preservation.” It is the old identity heuristic, now diverging from the new explicit lineage.

Concrete counterexample (eligibility tests already build it): conflict G=`{first, second}`; `second` superseded by `third` on the same identity; no conflict successor. Eligibility evaluates `{first, third}`. Profile `generate()` must reject hanging `second`. Correction’s active set omits G. Three consumers, three answers.

Further: if remap collapses two members onto one current id, eligibility **silently drops** an unresolved conflict (`len(resolved) < 2`) without a correction commit. That is silent resolution in a current-head consumer.

Event/exposure conflicts never enter eligibility (`member_kind=="fact"` only). Source-only event/exposure successors therefore cannot be observed there at all.

**I2. Current-head duplication if a later run re-extracts both conflicting sides.**  
Run1: G1=`{F1,F2}`. Run2 publishes inherited F1′, F2′ (or two new candidates that map to those facts). `_publish_conflicts` inserts G_new=`{F1′,F2′}` as a root. Append then inserts Gs=`{F1′,F2′}` with `source_revision_of=G1`. `current_conflict_heads` returns **both** G_new and Gs. Unresolved state is not resolved, but it is duplicated. The existing test avoids this by inheriting only one side.

**I3. Fold-then-exclude is sound for source chains *or* correction supersession, not for a single lineage spanning both.**  
Source child then correction of the **current** head: ancestor is not a head, superseded head is excluded, ancestor is not revived (matches E2). Correction first (G1 superseded, G2 new root) then source-append of G2: also fine. What is not encoded: walking `source_revision_of` from the live head through a correction. Correction breaks that chain by design (E8). A consumer that assumes “one parent pointer explains all history” will misread post-correction source growth.

Do not later unify correction onto `source_revision_of` without changing `source_conflict_heads`’s `gate_id` equality: event/exposure correction tests require `successor.gate_id != old_gate`. That unification would fail-close the entire authority.

**I4. Storage gates for the implemented source path are mostly fail-closed; tests do not pin the members.**  
Drop-one-member, duplicate id, restore old ids, mix event ids, bump `resolution_revision`, skip revision, fork: covered as `create()` negatives on an already-built successor (E5). Missing: third revision (`Gs2.source_revision_of==Gs1`, `revision==3`, G1 and Gs1 unchanged, head=Gs2); event/exposure source append; corrected member in a live conflict (expect publication refuse, not ancestor inherit); source then correction (supersede Gs, not G1; Profile shows correction successor or none, never G1); correction then source; two-sided re-extract (I2); exact locator equality (test uses `>=`); successor `fact_ids` must contain the new inherited id **and** the unchanged other id; `gate_id` frozen on source path.

Permutation no-op: if `old_ids` and `new_ids` are the same set in different order, list inequality would let validation treat it as source growth (E10). Contract sorting makes this unlikely for newly created rows; it is still a weaker predicate than `set(new)==set(old)`.

**I5. Caller transaction is Runner-owned; the test savepoint is not the product path.**  
`FactPublicationError` inside `session.begin()` rolls back facts, event/exposure successors, and the conflict successor together. Adding `begin_nested` inside `publish()` would split that. The missing-successor test’s nested transaction is a test harness, not a second product boundary. I do not treat that 193-test run as covering I1–I3.

**I6. “All-member preservation” is list-length preservation of the prior group, not preservation of the clinical conflict universe.**  
Source append cannot add a third party to G1 (length check). A new incompatible value in the later run becomes a **new root** via `_publish_conflicts` (E9), which may be clinically a three-way conflict shown as two groups. That is neither silent resolve nor all-member preservation of the original group; it is split representation. Codex must decide if that is acceptable.

---

### Recommendation

Advisory only. Implementation requires a Codex edit round.

1. **Retire implicit identity remap in eligibility (and stop testing it as success).** After `current_conflict_heads`, evaluate **stored** member IDs only. If members are not ⊆ current fact/event/exposure heads, fail the projection (same invariant as Profile) or skip the group only when a correction commit superseded it. Delete or invert `test_projection_keeps_mixed_revision_conflict_on_head_members` / `test_projection_skips_fully_superseded_conflict_groups` so they cannot pass without an explicit conflict successor. Do not keep a compatibility remap “for fixtures.”

2. **Make `_publish_conflicts` successor-aware in the same transaction.** After (or before) append, refuse or skip a new root whose member set is equal to a just-written source successor (or whose semantic key is already represented by a live source head with the same members). Fail closed on ambiguity; do not emit two current heads for one preserved group.

3. **Keep correction successors as a separate type until Codex explicitly redesigns lineage.** Do not set `source_revision_of` on correction rows while `gate_id` may change. Document that `current_conflict_heads` = source-fold ∪ correction-exclude, not one linked list.

4. **Required tests (these are the counterexamples; the green one-sided fact test is not coverage).**  
   - Third source revision: head=Gs2, `revision==3`, parent=Gs1, G1/Gs1 bytes unchanged, Profile succeeded, eligibility uses Gs2 members with no remap.  
   - Event conflict + fact inheritance → event source successors → conflict source successor; same for exposure; `gate_id` unchanged; locators = member union.  
   - Source append then correction of a member: superseded id is the **source head**, not the ancestor; ancestor not in `current_conflict_heads`; Profile does not show G1.  
   - Correction then source append of the correction root: new source child, correction root not revived if later superseded.  
   - Two-sided later run: not two current heads with the same member set.  
   - Eligibility hanging members: must not remap; must fail or require successor.  
   - Corrected current fact cannot be a source-conflict parent; publication refuses; no ancestor inherit.  
   - Replay of the source-successor run after that correction: replay, not a new child of a superseded head.  
   - Pin successor `fact_ids` (new inherited + unchanged other), `gate_id==prior.gate_id`, `resolution_revision==0`, locator equality.

5. **Tighten validation predicates.** Reject `set(new_ids)==set(old_ids)` even if order differs; after the event/exposure loop, assert `not unmatched`; reject duplicate `inherited_from` keys in the replacement dict (two children of one parent is a fork, not last-wins).

Default product choice if Codex must pick without more input: **eligibility fail-close + no duplicate roots**, matching Profile and §17.5 “不得无说明丢失 / 不能拼入无候选旧定位 / 冲突不闭合则整笔拒绝.” Do not keep identity remap as a second proof.

---

### Uncertainty

- Did not execute tests or JobRunner; transaction rollback is inferred from `session.begin()` + the nested-test behavior, not re-measured here.  
- Did not inspect live isolation DB 24-reference cases; those remain outside this pass.  
- Whether a later run’s new semantic conflict with a **superset** of remapped members (F1′ vs F3 plus Gs=`{F1′,F2}`) should stay as two groups is a product decision, not proven by code comments.  
- Whether event/exposure conflicts should appear in eligibility at all is unspecified by this packet; they are currently dropped.  
- `list_for_authority` plus `source_conflict_heads` fail the whole authority on one forked/missing-parent historical row; that is fail-closed, but the operational blast radius was not tested.

---

### Objections (highest first)

1. The plan’s assumption “Profile、审核投影和更正接入同一当前冲突选择” is only true for **which group id is head**. Eligibility still proves currency by `stable_identity` substitution; that contradicts the assigned rule “do not accept implicit same-identity replacement as proof.”  
2. One green fact-conflict append test plus a 193-test adjacent run does not exercise third revision, event/exposure conflicts, or correction×source replay — the cases this conference was opened for.  
3. `_publish_conflicts` then append can mint two live unresolved groups for the same members; that is a current-head bug, not preservation.  
4. Correction’s new-root successor with a changed `gate_id` will poison `source_conflict_heads` if someone “simplifies” it onto `source_revision_of`. Do not do that as a drive-by unification.

---

### Decision points for Codex

- D1: Eligibility hanging members: fail-close like Profile, or keep remap? **Recommend fail-close.**  
- D2: Same-member new root vs source successor in one publish: refuse, skip new root, or allow duplicates? **Recommend refuse or skip; never two heads.**  
- D3: Correction lineage: keep separate root + `conflict_outcomes`, or merge into `source_revision_of` (requires relaxing `gate_id` fold)? **Recommend keep separate.**  
- D4: New third incompatible value in a later run: new root alongside the preserved two-member successor, or fail until an explicit multi-member revision exists? **Needs a product call; current code does the former.**

---

### Bounded questions for Codex

1. For D1, should `EligibilityReviewProjectionService.project` raise (block the review view) or return an explicit gap when a current conflict head cites non-head members? Profile raises; a softer skip would again hide unresolved conflicts.  
2. For D2, is “same member set” the identity, or must semantic_key also match (in case two groups share members for different reasons)?  
3. After a correction successor (new root, new gate), is a later source-only child of **that** root in scope for this R06 pass, or deferred until correction×source tests exist? Safe provisional path: treat it as in-scope for tests, out-of-scope for merging the two successor types.

Safe provisional path if Codex does not answer this turn: do not accept R06; do not edit production; do not treat `test_source_append_with_unreconciled_conflict_rolls_back` as closure; next authorized edit should kill eligibility remap and add the third-revision + event/exposure + duplicate-root tests before any clinical/library claim.
