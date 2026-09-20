I’ll re-audit only the files Codex named for this continuation: eligibility projection, publication ordering/conflicts, successor validate/append, and the new correction/replay tests.Eligibility remap is gone and successor validation is tighter. Next I’ll read publication ordering, conflict skip logic, and the new tests.Round-1 eligibility remap and identical-member duplication are addressed in the named files. Remaining review is skip provenance, dual lineage, replay, and untested third-value overlap.# Conference Output: r06-conflict-source-review-20260913 - evidence_single_object

## Output

Read-only continuation (round 2). No source edits, no tests executed here, no clinical DB/originals, no visual/browser acceptance. Codex remains final authority.

This pass re-read only the named deltas plus the minimum dependents: `app/services/eligibility_review_projection.py` (`_phase3_conflict_groups`, `project`), `app/services/fact_publication_service.py` (publish order, `_publish_conflicts`, `_replay_if_published`), `app/services/source_conflict_successors.py`, `app/storage/source_conflict_successors.py`, `tests/v2/services/test_fact_publication_service.py` (source-append / event-exposure growth), `tests/v2/services/test_source_conflict_corrections.py`, `tests/v2/services/test_eligibility_review_projection.py` (inverted stale tests), `tests/v2/domain/test_phase5_fact_contracts.py` (legacy conflict decode), `app/storage/source_reference_successors.py` (`validate_source_fact_references` predicate still used by conflict validation), `app/services/fact_correction_service.py` (active-set filter only), `app/domain/gates/assessment.py` (conflict_groups loop), `app/services/fact_normalization_executor.py` (FactPublicationError wrap). Prior-round files were not re-scanned except where a remaining claim depends on them.

Owner decisions taken as binding for this round: eligibility identity remap removed and stale members reject the projection; source vs correction lineage stay different relationships; a genuine third-value dispute stays a separate group; event/exposure-to-clause assessment stays an open issue.

Round-1 I1 (eligibility remap) and I2 (identical-member duplicate current heads from `_publish_conflicts` before append) are **retired as current defects**. They are not R06 or clinical closure.

---

### Evidence

**E1. Eligibility no longer remaps members.**  
`_phase3_conflict_groups` still uses `current_conflict_heads`, still drops `member_kind != "fact"` (declared open), then requires `set(fact_ids) <= active_fact_ids` and raises `EligibilityReviewProjectionError("争议资料与当前病史尚未完整衔接，不能生成审核结果")` (`eligibility_review_projection.py` 287–304). The `head_of_fact` / `len(resolved) < 2` skip path is gone. `test_projection_rejects_mixed_revision_conflict_without_successor` and `test_projection_rejects_all_stale_conflict_members_without_successor` invert the old success cases to that error (409–458). Live current members still project as `source_conflict` (380–406).

**E2. Source successors are appended before new-root detection; identical member tuples are not inserted again.**  
`publish()`: if any published fact has `inherited_from_fact_id`, it appends event/exposure source successors, then conflict source successors, **then** `_publish_conflicts(..., source_successors=published_conflicts)` (`fact_publication_service.py` 289–312). `_publish_conflicts` builds `preserved_members` as `(member_kind, tuple(sorted member ids))` from those successors and `continue`s before `repository.create` when the newly mapped set matches (684–700). New roots still use `conflict:` + this-run `semantic_key` hash and this-run `min(gate)` (708–730).

**E3. Append/validate now reject forks and set no-ops.**  
Append: one parent → one child, else `InvalidReferenceError("同一来源存在多个后继，不能选择其中之一")` (`source_conflict_successors.py` service 16–24). Validate: `set(old_ids) == set(new_ids)` rejected; event/exposure loop asserts leftover `unmatched` (storage 33–62). Locator equality to member union remains (63–65). Gate dump still frozen (not in `mutable`).

**E4. Tests now pin three revisions, members, gate, locators, and both-sides skip.**  
Fact path parametrizes `both_sides` and `missing_successor` (`test_fact_publication_service.py` 1209–1354): successor `fact_ids` = new inherited ∪ unchanged other; `gate_id` frozen; locators = member union; `revision` 2 then 3 with parent = previous successor; old rows unchanged; current head = latest; same-run replay; missing append still rolls back via nested savepoint. Event/exposure path (`1357–1430`) runs revisions 2 and 3, asserts both members’ `source_revision_of` equal the previous member ids, same original gate, locator union, Profile `succeeded`.

**E5. Correction sequence uses the real job/runner and keeps the two lineage types apart.**  
`test_source_growth_then_correction_then_source_growth` (one test): source successor of the first group; `FactCorrectionJobService` + `_run`; correction successor has `source_revision_of is None` and is the only current head; `publish(source_run.run_id).is_replay`; further source growth parents the **correction root**, same correction `gate_id`, `resolution_revision==0`, first group id not in current heads; Profile `succeeded`. No eligibility call in that file.

**E6. Replay still returns that run’s persisted rows, including superseded conflict ids.**  
`_replay_if_published` is invoked on unfiltered `existing_*` before superseded filters (`fact_publication_service.py` 197–234). It selects `run_id` matches, subtracts parent candidates of inherited facts, and returns `conflict_group_ids` of **all** conflicts with that `run_id` (345–385). It does not consult `current_conflict_heads`.

**E7. Legacy conflict JSON without the new fields still decodes.**  
`test_conflict_group_requires_at_least_two_facts_and_is_unresolved_by_default` encodes a dump excluding `source_revision_of`/`revision`; restore is `None` / `1` with remaining payload equal (`test_phase5_fact_contracts.py` 645–661).

**E8. Clause gaps use the conflict **list**; fact badges keep one group id.**  
`derive_gate_gap_types` iterates every `conflict_groups` entry (assessment.py 264–266). `conflict_group_by_fact.setdefault` still assigns each fact a single group (`eligibility_review_projection.py` 344–346). Groups with no `affected_rule_component_ids` are omitted from the list (`continue` at 333–334), not raised.

**E9. Correction’s “current projection” set still omits a current head whose members are not ⊆ current entity ids** (`fact_correction_service.py` 253–264). Publication+Profile fail-close that state on the source path; eligibility now raises on read.

**E10. Runner still wraps only `FactPublicationError`.**  
Fork at append raises `InvalidReferenceError`; storage failures raise `FactCrossEntityError`. Executor maps `FactPublicationError` to `StepFailure` (`fact_normalization_executor.py` 1271–1278). Any exception still aborts `session.begin()`; the user-facing publication message is not applied to the fork path.

---

### Inference

**I1. Round-1 highest defect is fixed on the named path.**  
Stale conflict members can no longer be “proved current” by `stable_identity`. That was the assigned forbidden implicit replacement. Event/exposure conflicts remain invisible to eligibility by filter, which the owner marked open — not a regression of this patch, and not completeness.

**I2. Identical-member duplication is gone for this-run source successors; skip has no durable detection row.**  
Both-sides reread: append writes `source-conflict:…` with this `run_id` and **prior.gate_id**; `_publish_conflicts` does not create a parallel `conflict:…` root with this-run `min(gate)` / `semantic_key`. Current heads stay one group. That matches the owner skip rule.

What skip does **not** record: that `detect_semantic_conflicts` fired, which `semantic_key` was absorbed, or the unused this-run conflict gate. Provenance of the dispute after skip is the successor row (`run_id` = this run, `source_revision_of` = prior, frozen original gate, unioned fact candidates on members). That is consistent with “source-only does not mint a new clinical gate.” It is **not** a demonstrated wrong current-head state.

This is a **missing audit/test pin**, not a demonstrated error: no assert that `list_by_episode` after both-sides contains only the prior group plus `source-conflict:` (no extra `conflict:` row). `len(published.conflict_group_ids)==1` plus `current_conflict_heads==[successor]` already implies no second **current** head; it does not document the skip as an explicit event.

Skip compares only **this-run** successors, not already-live heads. Same-identity re-extract goes through inheritance + append first, so the live head is updated before skip. A new root with a **different** member tuple (third value) is not skipped. That matches the owner third-value rule. **No test publishes a third incompatible value and asserts two current heads** (successor keeps the old pair; new group has the new member; old member not dropped). That is missing coverage of a stated owner decision, not a demonstrated drop/adjudication.

**I3. Source vs correction history is implemented as two relations and the one runner test matches it.**  
Source child: `source_revision_of` + `revision+1` + frozen gate. Correction child: new root, `source_revision_of is None`, `gate_id` may change, link is `conflict_outcomes.superseded_conflict_group_id`. Fold-then-exclude therefore cannot revive G1 after Gs is superseded. Later source growth parents the correction root, not G1. Demonstrated for **one-sided fact** correction, not for event/exposure correction×source, not for correction that resolves (`successor_id is None`) then later source growth.

**I4. Old-run replay after correction is historically correct and must not be read as current heads.**  
Replay of `source_run` after the correction commit is asserted `is_replay` (E5–E6). It will return the **source successor id**, which is superseded, not `correction_group`. That is the right replay of what that run persisted. A caller that treated `FactPublicationResult.conflict_group_ids` as `current_conflict_heads` would be wrong; Profile/eligibility/correction selection do not use that list. **Not demonstrated as a product bug.** Missing pin: after replay, `current_conflict_heads` still equals `[correction_group]` and Profile still hides G1/Gs.

**I5. Remaining consumer split is narrower and mostly fail-closed.**  
Unclosed members: publication refuses; Profile refuses; eligibility now refuses; correction impact-set still **omits** such a group (E9). That omit cannot resurrect an ancestor; it can make a later correction job skip recomputing a dangling head and then fail Profile generate. Direct `repository.create` fixtures can still build that state (eligibility tests do). Product path after this patch should not commit it.

Shared member across two current fact groups (third-value + preserved pair): clause `SOURCE_CONFLICT` can still fire from the full `phase3_conflicts` list (E8). The fact’s single `conflict_group_id` badge can name only the lexicographically first group. **Missing test**, possible UI/marker inconsistency, not silent resolution.

**I6. `validate_source_fact_references` still uses list equality `current_ids == prior_ids`.**  
Conflict-level set no-op now blocks permutation-as-update for the group. The helper leftover cannot accept a set-equal permutation on the conflict create path because that path returns first. Not a demonstrated conflict-successor hole.

**I7. Narrow source-only path is supportable as engineering, not as R06/clinical acceptance.**  
For: explicit parent, all members kept, no `resolution_revision` bump, original gate/locators pinned, identical this-run roots not duplicated, eligibility stale refs reject, correction not folded into `source_revision_of`, three-revision fact/event/exposure tests, one real-job correction sandwich, legacy decode, runner-owned transaction (exception still rolls back).  
Against closure: third-value separate-group untested; skip has no audit tuple; event/exposure eligibility open; correction×source not generalized; 193/209/1 passing counts are adjacent engineering, not originals/QC.

---

### Recommendation

Advisory only.

1. **Treat the narrow source-only path as supportable to keep, not to close R06.** Do not claim whole-workflow or clinical acceptance from the 1+193+209 snapshots.

2. **Skip provenance — do not add a second current group.** If Codex wants the skip inspectable, pin tests (both_sides: episode conflict rows = `{prior, source-successor}`, ids start with `source-conflict:`, `gate_id==prior.gate_id`) rather than persisting a skipped `conflict:` root. An optional debug/audit field is a product add, not required to keep current-head correctness.

3. **Add the third-value test the owner already decided.** Same run (or a later run) publishes a new incompatible value **and** source-grows the old pair: current heads length 2; old successor still has both original parties (remapped); new group contains the third id; neither old member dropped; Profile succeeded; eligibility either marks conflict via the list or fail-closes on members — **not** identity remap.

4. **Pin replay vs current heads in the correction test:** after `publish(source_run).is_replay`, `current_conflict_heads == [correction_group]` and replay ids are a subset of history, not of current heads. Same after the post-correction source child.

5. **Do not unify correction onto `source_revision_of`.** Event/exposure correction still changes `gate_id`; `source_conflict_heads` still requires gate equality. Leave as two relationships.

6. **Missing but not blocking for this patch:** eligibility after the correction sandwich; event/exposure × correction × source; wrap append `InvalidReferenceError` as `FactPublicationError` for executor wording; correction-omit vs eligibility-raise on hand-built dangling heads. Event/exposure-to-clause remains the declared open issue.

---

### Uncertainty

- Tests were not re-run in this session; pass counts 1 / 193 / 209 are taken from the continuation prompt, not reproduced here.  
- Third-value overlapping groups and skip-vs-`list_by_episode` were not observed at runtime.  
- Whether `detect_semantic_conflicts` in one run with three candidates emits one 3-member group (plus a 2-member successor) or pairwise groups is unread beyond this-run candidate aggregation; the third-value test should fix that empirically.  
- Isolation-library 24-reference cases, live JobRunner publication of real conflicts, and clinical QC remain out of scope.

---

### Round-1 challenges (what stands / what is withdrawn)

| Round-1 claim | Round-2 status |
|---|---|
| Eligibility identity remap is a live proof | **Withdrawn as current code defect.** Remap removed; stale tests inverted to reject. |
| `_publish_conflicts` before append duplicates identical members | **Withdrawn.** Order reversed; identical tuple skipped. |
| Third revision / event-exposure source growth untested | **Withdrawn as omission of tests.** Now present (E4). |
| Correction vs source lineage mixed | **Withdrawn as implementation contradiction.** Two types preserved; one runner test (E5). |
| Skip/third-value/replay-as-current | **New, narrower.** Skip correctness demonstrated indirectly; skip audit and third-value **missing tests**. Replay-as-history is correct (I4). |
| Event/exposure eligibility | **Still open**, per owner; do not treat this patch as completing it. |

---

### Objections

1. “193 then 209 then 1 passed ⇒ R06” — those are synthetic contract checks. They do not inspect originals or the 24-reference isolation set.  
2. Skip without a row is not silent **resolution** (members and unresolved flag remain on the successor). Calling it a provenance hole is fair; calling it adjudication is not.  
3. `conflict_group_by_fact.setdefault` plus two current groups is the leftover consumer inconsistency if the third-value test is added and both groups share a fact. Clause gaps still see both groups.

---

### Decision points / bounded questions

- Q1: Is “skip = no extra row” enough provenance, or must both-sides tests assert episode history ids? **Provisional: history pin only, no new entity.**  
- Q2: Third-value in the **same** run as a 2-member successor: allow overlapping groups, or fail until an explicit multi-member **source** revision exists? Owner text says keep a separate group and never drop the old member — overlapping current heads are the literal reading. **Needs the test before any further code.**  
- Q3: After correction, may replay `conflict_group_ids` appear in any current UI? If yes, that would be a consumer bug; if only Profile/`current_conflict_heads` are shown, I4 is closed. Not verified in UI (out of this role).

Safe provisional path: keep the patch; do not close R06; do not merge lineage types; next authorized work is the third-value current-head test and a replay-vs-current-head pin, not eligibility event/exposure clauses.
