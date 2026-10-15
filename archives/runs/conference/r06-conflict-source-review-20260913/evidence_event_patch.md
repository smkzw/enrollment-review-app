I'll inspect the current diff and the named eligibility/workbench files against the prior consume-without-clause-binding recommendation.The worktree diff is mixed with unrelated files. I’ll read the current eligibility projection, API, frontend types/view-models/page, and tests in full.# Conference Output: r06-conflict-source-review-20260913 - evidence_single_object

## Output

Read-only implementation check of event/exposure conflict **consumption** (not a re-audit of source successors). No writes, no test re-run, no browser, no clinical DB. Pass counts 93/67.18s and frontend 15/2.36s taken from the prompt. Codex remains final authority. Browser of the new banner is pending and is not visual acceptance.

Inspected current definitions: `app/services/eligibility_review_projection.py` (envelope + closure + `_phase3_conflict_groups` + `project`), `app/api/v2/eligibility_review.py`, `frontend/src/api/eligibility-review/eligibilityReviewTypes.ts`, `eligibilityReviewViewModels.ts`, `eligibilityReviewHttp.test.ts`, `frontend/src/pages/EligibilityWorkbenchPage.tsx` (+ test), `app/services/patient_profile_service.py` (`_published_events` / `_published_exposures` / `_validate_referential_closure`), `frontend/src/app/routes.tsx`, `frontend/src/pages/SubjectsPage.tsx` (query contract), `tests/v2/services/test_eligibility_review_projection.py` (new parametrize + retained fact/future tests), `tests/v2/api/test_eligibility_review.py`.

---

### Blocking findings

**None within the inspected consumption scope.**

No fact-link fan-out onto clauses. No identity remap of stale members. No 409 of a well-formed event/exposure current head. No circular import. Envelope does not set per-clause `gap_type`. Workbench notice does not declare unrelated clauses in conflict.

---

### Evidence

**E1. Closure is Profile selectors, but only members of non-fact current heads.**  
`project()` loads `current_conflict_heads`, keeps `member_kind != "fact"` as `unassigned_groups`, then (only if that list is non-empty) calls `PatientProfileService._validate_referential_closure` with `facts=current_fact_heads`, events/exposures **filtered to ids appearing on those groups**, `conflicts=unassigned_groups`, `expectations=[]` (`eligibility_review_projection.py` 649–670). Failure is wrapped as existing `EligibilityReviewProjectionError` → API 409 `REVIEW_SOURCE_INCOMPLETE` (`eligibility_review.py` 110–112). Unrelated events are not closed here. That matches the stated “selected conflicting entities only” choice.

**E2. Evaluator path for facts is unchanged.**  
`_phase3_conflict_groups` still facts-only, still fail-closed on stale fact members, still `list_for_facts` → `affected_rule_component_ids` (`eligibility_review_projection.py` 290–359). `derive_gate_gap_types` still receives only those Phase-3 groups (`705–710`). Event/exposure `fact_ids` are not unioned into that set.

**E3. Envelope is current ids, not clause assignment.**  
`EligibilityUnassignedConflict` / DTO: `conflict_group_id`, `member_kind` in `{event, exposure}`, `member_ids` min 2 unique (`eligibility_review_projection.py` 152–156, 767–774; `eligibility_review.py` 65–76). Fact groups never enter it. `to_dict`/`asdict` keeps those fields. Frontend decode: missing key → `[]`; `member_kind=fact` or duplicate member ids → `EligibilityReviewDecodeError` (`eligibilityReviewViewModels.ts` 232–245; `eligibilityReviewHttp.test.ts` 40–50).

**E4. Workbench notice is separate from the tree.**  
Banner copy: “有 N 项病史或用药记录不一致，尚未确定影响哪些条款。” Link `/profiles` with the **same query** as the current-node 资料页 link; `private-conflict` ids must not appear (`EligibilityWorkbenchPage.tsx` 704–712; test 129–141). `/profiles` is `SubjectsPage` (`routes.tsx` 104–108), which reads `project`/`subject`/`episode` (`SubjectsPage.tsx` 8, 187–223).

**E5. Synthetic tests cover the required counterexample and stale refs; they do not cover correction heads on the envelope.**  
`test_non_clause_conflicts_preserved_without_fact_link_fanout` (`test_eligibility_review_projection.py` 43–82): shared age fact + two events/exposures with different dates; `after.clauses == before.clauses`; one envelope row with stored group id/kind/member ids; group row not deleted. `stale=member` monkeypatches `_published_events`/`_published_exposures` to one member; `stale=fact` publishes a superseding fact so member `fact_ids` are non-head → projection error. Retained: `test_projection_reverses_conflict_members_to_component` (465), `test_projection_marks_future_clause_not_due_and_missing_judgment_summary` (417). Backend GET 200 test does **not** assert `unassigned_conflicts`.

**E6. Imports.**  
`PatientProfileService` is imported **inside** `project()` (`650`). `patient_profile_service.py` does not import eligibility. No cycle at module or that call. Selectors used are `_published_*` / `_validate_referential_closure` (not in `PatientProfileService.__all__`). `ClinicalConflictGroupV2Repository` is imported in eligibility projection (`50–52`) and unused.

---

### Inference

**I1. Prior recommendation vs what landed.**  
Adopted: no `fact_ids` fan-out; fail-closed dangling **conflict members** (and their fact refs); single evaluator; envelope rather than per-clause `SOURCE_CONFLICT` or sprayed `PROVENANCE_FOLLOWUP`; no `consumes_event_types` fields; no id rewrite/group delete. Envelope + Profile link is the optional DTO path, not Profile-only. Checking only conflict members (not every episode event) is a deliberate narrowing of my earlier “members’ fact_ids ⊆ current facts” wording; it will **not** 409 eligibility for T3-style hanging events that are not in a current event/exposure **conflict**. That is consistent with “do not block the whole tree,” and is not a false clause assignment.

**I2. Correction heads.**  
Envelope source is `current_conflict_heads` (`649–653`), which already fold-then-exclude superseded ids. A correction successor that is a new root (`source_revision_of is None`) would appear as the unassigned row; the superseded source head would not. That is not demonstrated by `test_source_conflict_corrections.py` against this envelope. Not a demonstrated wrong implementation, a **missing pin**.

**I3. Stale/missing envelope semantics are fail-closed or empty, not remapped.**  
Missing wire field → UI `[]` → no banner. Present well-formed event/exposure current head → banner + Profile link, clauses unchanged (E3–E5). Absent/old member or old fact on a **selected** conflict member → 409, no clause list (`test_eligibility_review.py` 74–88 still the API mapping). Empty `unassigned_conflicts: []` is the success shape; I did not see a GET assertion for that key.

**I4. False clinical assignment is not present in the inspected path.**  
Happy-path `clauses == before.clauses` is the non-conflict counterexample. Banner language is “尚未确定影响哪些条款,” not `decision=conflict`. Future clauses keep the existing early-return in `derive_gate_gap_types` because event groups never enter `conflict_groups`.

**I5. Private-selector coupling is real and tested, not circular.**  
Monkeypatch of `PatientProfileService._published_events` is the stale-member test. If those methods are renamed or start generating Profile rows, eligibility breaks loudly. That is acceptable reuse for this slice, not a blocking defect.

---

### Recommendation

Keep this slice. Do not add requirement consume-fields or clause fan-out.

Non-blocking follow-ups (not R06 closure):

1. Backend GET 200: `unassigned_conflicts == []` on the existing wire test; a fixture with a live event group asserts the envelope and unchanged `clauses[].gap_type`.  
2. Correction: after the existing job sandwich, eligibility envelope is the **correction root** (or empty if resolved), never the superseded source head.  
3. Frontend decode: reject duplicate `conflict_group_id` (API already does, `eligibility_review.py` 96–98).  
4. Drop unused `ClinicalConflictGroupV2Repository` import.  
5. Browser of the banner still pending; do not treat the unit test’s `href` equality as visual acceptance.

---

### Uncertainty

- 93/15 pass counts not reproduced here.  
- Isolation 24 dangling **non-conflict** events still will not 409 this GET (I1); Profile generate may still fail — that split is now explicit.  
- Banner layout/contrast unread in a browser.

---

### Precise tests still needed

| Gap | Why |
|---|---|
| API GET empty and non-empty `unassigned_conflicts` | Service test does not prove the DTO round-trip |
| Envelope after correction supersession | Head selection is inferred from `current_conflict_heads`, not pinned here |
| Duplicate `conflict_group_id` on the client | Decode hole vs API |
| Browser notice + `/profiles` same-node Profile highlight | Prompt: pending; not acceptance |

**Narrow consumption path is supportable** as implemented: truthful unassigned association, no false clause conflict, fail-closed selected dangling refs. Not clinical/R06 acceptance.
