I'll audit event/exposure conflict consumption only: how groups are filtered, how fact-to-clause links work, and whether propagating `fact_ids` would overclaim disputed attributes.I have the consumption path: fact-only clause binding, Profile already listing all member kinds, and no event-to-requirement fields on published rules. The report will recommend fail-closed members plus Profile/envelope display, not `fact_ids` fan-out.# Conference Output: r06-conflict-source-review-20260913 - evidence_single_object

## Output

Read-only follow-up on **event/exposure conflict consumption** only. Prior source-successor findings are retained, not re-audited. No edits, no DB/originals, no clinical acceptance. Codex remains final authority.

Read this round: `app/services/eligibility_review_projection.py` (`_phase3_conflict_groups`, `project`, gap policy), `app/domain/contracts/facts.py` (event/exposure/conflict), `app/domain/contracts/evidence.py` (`ConflictGroup`, `ClinicalFact`), `app/storage/active_conflicts.py`, `app/storage/fact_rule_link_repository.py` (actual repository; there is no `fact_rule_link_repositories.py`), `app/domain/contracts/fact_rule_index.py` (`derive_fact_rule_links`), `app/domain/gates/assessment.py` (`derive_gate_gap_types`, `derive_component_decision`), `app/domain/policies.py` (blocking vs `PROVENANCE_FOLLOWUP`), `app/domain/contracts/rules.py` (`EvidenceRequirement`), `app/domain/expression.py` (`EvaluationContext`), `app/projections/patient_profile.py` (`_conflict_item`, highlights), `app/services/patient_profile_service.py` (`_published_conflicts`), `app/api/v2/eligibility_review.py`, `app/services/evidence_app_errors.py`, `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §17.5, `artifacts/review-20260912/T3_CUMULATIVE_PROFILE_20260913.md`, related eligibility/profile tests.

---

### Evidence

**E1. Eligibility still drops every non-fact current head.**  
`current_conflict_heads` returns fact/event/exposure groups (`active_conflicts.py` 32–42). `_phase3_conflict_groups` then keeps `member_kind == "fact"` only (`eligibility_review_projection.py` 289–296). Event/exposure groups never reach `derive_gate_gap_types`. Fact groups with members not ⊆ current fact heads raise `EligibilityReviewProjectionError` (301–306); API maps that to 409 `REVIEW_SOURCE_INCOMPLETE` (`eligibility_review.py` 92–94; `evidence_app_errors.py` 91–98). Tests invert stale fact members to that error (`test_eligibility_review_projection.py` 409–458). No event/exposure analogue in that file.

**E2. Clause conflict is only “component id ∈ ConflictGroup.affected_rule_component_ids”.**  
Phase-3 `ConflictGroup` requires `fact_ids` length ≥ 2 and `affected_rule_component_ids` length ≥ 1 (`evidence.py` 309–314). `derive_gate_gap_types` adds `SOURCE_CONFLICT` iff that membership holds (`assessment.py` 264–266). That gap forces `ComponentDecision.CONFLICT` (`assessment.py` 296–297, 321–333) and is first in eligibility `_GAP_PRIORITY` (`eligibility_review_projection.py` 75–76). Frontend RuleTree treats `source_conflict` as blocking. Future-only components return `{FUTURE_STAGE_NOT_DUE}` **before** the conflict loop (`assessment.py` 259–262) — fact conflicts already do not block not-due clauses.

**E3. Fact→component links are fact_type + explicit requirement ids, not event/exposure attributes.**  
`derive_fact_rule_links` joins `supported_requirement_ids` and `PublishedRequirement.fact_type == fact.fact_type` (`fact_rule_index.py` 146–178). `EvidenceRequirement` has `fact_type`, `due_stage`, source flags — **no** `event_type`, duration, dose, or exposure identity (`rules.py` 279–288). Events/exposures carry their own disputed fields (`start_range`/`end_range`/`duration_status`; exposure also dose/route/…) plus `fact_ids` (`facts.py` 439–553). Evaluator `EvaluationContext` accepts only `ClinicalFact` (`expression.py` 33–46). `ClinicalFact.conflict_group_id` is a single optional badge (`evidence.py` 257).

**E4. Profile already consumes all member kinds without rewriting ids.**  
`current_conflict_heads` → `_conflict_item` uses `fact_ids + event_ids + exposure_ids`, `conflict_member_kind`, and highlight `unresolved_conflict` when `resolution_revision == 0` (`patient_profile.py` 196–213, 294–297). Closure still refuses hanging event `fact_ids` (§17.5 / T3: 24 isolation events cite non-head facts; do not remap). Source successors for events/exposures remain explicit parents (prior rounds).

**E5. `PROVENANCE_FOLLOWUP` is the existing non-blocking reminder, not a confirmed conflict.**  
It is stripped from blocking gaps (`assessment.py` 321; `policies.py` 204–242). Eligibility copy treats it as “需溯源核对” (`eligibility_review_projection.py` 88, 106, 587–588). Spraying it onto every due clause would still **claim** those clauses need provenance follow-up.

---

### Inference

**I1. Walking each event/exposure `fact_ids` through `FactRuleLinkV2Repository.list_for_facts` is not sufficient provenance. It overclaims the disputed attribute.**  
Concrete counterexample (must be a test, not implemented): two events share one base fact (e.g. diagnosis object); they conflict only on `duration_status` / dates (`facts.py` 480–487 identity includes those fields). That same fact is linked to an unrelated numeric/demographics component via `fact_type`. Fan-out would put that component in `affected_rule_component_ids` → `SOURCE_CONFLICT` → `decision=conflict`. The evaluator never read event dates. Same for one fact supporting several requirements: every linked component would inherit an event-date dispute. That is a new silent clinical claim, worse than today’s filter.

**I2. Confirmed clause conflict vs truthful unresolved association are already two mechanisms. Do not merge them for events/exposures.**  
| | Confirmed relevant clause conflict | Truthful unresolved association |
|---|---|---|
| Provenance | Fact group members ⊆ current facts **and** `FactRuleLink` `target_kind=rule_component` in the current ClausePack (`eligibility_review_projection.py` 314–336) | `ClinicalConflictGroupV2` current head, `member_kind` event/exposure, members current, `resolution_revision==0` |
| Consumer | `derive_gate_gap_types` → clause `gap_type=source_conflict` | Profile `ProfileItemKind.CONFLICT` + `UNRESOLVED_CONFLICT` |
| Must not | Identity-remap members; invent event–clause links | Mark unrelated / future clauses `SOURCE_CONFLICT` or 409 the whole tree |

Today’s filter is **drop**, not remap. Drop hides the dispute on the eligibility tree; Profile still has it **if** generate succeeded. Isolation 24-event dangling refs are a **closure** 409/Profile failure, not a license to rewrite `fact_ids`.

**I3. Smallest coherent next patch is consume-for-closure + display-without-clause-binding, not a new engine.**  
Do not add `EventRuleLink` / auto-binding. `EvidenceRequirement` has no consumes-event fields to derive from (`rules.py` 279–288). §17.5 forbids algorithm mapping posing as revision.

**I4. 409 the GET only for incomplete references, never because a well-formed event/exposure conflict exists.**  
Dangling event/exposure **members** (or those members’ `fact_ids` not ⊆ current facts) = same honest 409 as stale fact-conflict members. A closed event conflict with current members must **not** fail eligibility or flip future clauses to conflict (`assessment.py` 259–262 already protects not-due **if** we do not put those components in `affected_rule_component_ids`).

---

### Recommendation (minimal patch)

Implement only this, in `eligibility_review_projection.py` + tests; reuse existing selectors; no clinical DB; no id rewrite; no group deletion.

1. **Stop silent drop; fail closed on incomplete event/exposure groups.**  
   After `current_conflict_heads`, for every head:  
   - `fact`: members ⊆ `current_fact_heads` (existing).  
   - `event` / `exposure`: members ⊆ Profile’s current event/exposure heads (`patient_profile_service.py` 338–366 pattern: chain head then correction exclude). Those members’ `fact_ids` ⊆ current facts. Else raise the existing `EligibilityReviewProjectionError("争议资料与当前病史尚未完整衔接…")` so the API stays 409 `REVIEW_SOURCE_INCOMPLETE`.  
   Reuse `_validate_referential_closure` logic; do not duplicate a second selector.

2. **Keep a single evaluator path.**  
   Build Phase-3 `ConflictGroup` **only** from `member_kind=="fact"` via existing `list_for_facts` (`fact_rule_link_repository.py` 193–267). Do **not** union event/exposure `fact_ids` into that set. Leave `derive_gate_gap_types` unchanged. Do **not** set `ClinicalFact.conflict_group_id` from an event/exposure group.

3. **Preserve the dispute in UI without painting clauses.**  
   - **Already shipped:** Patient Profile CONFLICT items (`patient_profile.py` 196–213, 294–297). Eligibility workbench should keep showing Profile / EVIDENCE_QUALITY unresolved conflicts.  
   - **Optional wire, only if the eligibility payload must mention them without a Profile round-trip:** add an envelope list on `EligibilityReviewProjection` / `EligibilityReviewResponse`, e.g. `unresolved_non_clause_conflicts: [{conflict_group_id, member_kind, member_ids}]` for current event/exposure heads. `extra=forbid` means an explicit DTO field, not a silent extra. **Do not** put these ids into `clauses[].gap_type`. **Do not** attach `PROVENANCE_FOLLOWUP` to every due clause.

4. **If a later rule edition truly needs confirmed clause binding,** add **published requirement fields**, not a runtime binder:  
   `EvidenceRequirement.consumes_event_types: list[str] = []` and `consumes_exposure_keys: list[str] = []` (empty default). Derive component ids only when a **current-head member’s** `event_type` / exposure identity key is **explicitly listed** on that requirement, then feed the existing `ConflictGroup.affected_rule_component_ids` list. Until rule-set rows populate those lists, interim remains (1)–(3). No model bindings, no `stable_identity` rewrite of historical `fact_ids` (T3 / §17.5).

5. **Do not** use `PROVENANCE_FOLLOWUP` as a global banner-on-every-clause. That overclaims relevance and fights “do not classify all future clauses as blocked.” Future-only components stay `not_due` via the existing early return.

---

### Tests (including a valid non-conflicting counterexample)

Reuse `_publish_event` / `_publish_exposure` / conflict `create` from `test_fact_publication_service.py` and `test_fact_correction_job.py`; invert-stale pattern from `test_eligibility_review_projection.py` 409–458; API 409 from `test_eligibility_review.py` 74–88.

| Case | Expect |
|---|---|
| **C0 non-conflict (required).** Two events, **same** `fact_ids`, dispute only `duration_status`/`start_range`. Shared fact has `FactRuleLink` to IN-01 (numeric/demographics `fact_type`). No fact-level conflict group. | IN-01 **not** `source_conflict`. Other clauses unchanged. Profile has one CONFLICT item, `conflict_member_kind=event`. Eligibility GET 200. |
| **C1 confirmed fact conflict still works.** C0 plus a **fact** group on a different fact that **is** linked to IN-01. | IN-01 `conflict`/`source_conflict` from the **fact** group only. Event group still not in `affected_rule_component_ids`. |
| **C2 dangling event members or member `fact_ids` not current.** | Eligibility raises; GET 409 `REVIEW_SOURCE_INCOMPLETE`; no clause list; groups not deleted. |
| **C3 exposure dose/date conflict, fact linked to unrelated inclusion.** | Same as C0 for exposures. |
| **C4 future-only component** (no due requirement). | Stays `not_due` / `future_stage_not_due` despite a live event conflict. |
| **C5 superseded event conflict** (correction commit). | Absent from current heads; no 409; not on Profile. |
| **C6 envelope (only if DTO added).** | Lists event/exposure current heads; `clauses[].gap_type` not `source_conflict` unless C1. |

Do not add a test that “succeeds” by remapping old event `fact_ids` to current identity heads.

---

### Uncertainty

- Not verified in a browser this pass: whether the live workbench already shows Profile CONFLICT beside the eligibility tree. If it does, skip the DTO envelope (step 3 optional).  
- Whether isolation’s 9 conflicts include event/exposure kinds was not re-queried; T3’s 24 dangling **event fact refs** are Profile/publication closure, distinct from conflict-group consumption.  
- `ConflictGroup.fact_ids` min 2 cannot honestly represent an event pair; stuffing shared `fact_ids` into that field would also overclaim.  
- Rule-set `consumes_event_types` does not exist; populating it later is a protocol-contract change, not this patch.

---

### Objections / decision points

1. Fan-out via `fact_ids` looks small and is the wrong clinical claim (I1).  
2. 409 on well-formed event conflicts would block the entire tree, including future clauses — reject that.  
3. Envelope vs Profile-only: pick one display surface; do not do both plus per-clause gaps.

**Bounded question:** Must eligibility JSON itself list event/exposure current heads (DTO add), or is Profile `UNRESOLVED_CONFLICT` the approved UI for this slice? **Provisional:** Profile-only + fail-closed dangling refs; add envelope only if Codex confirms the eligibility page is shown without Profile.

**Narrow path supportable:** yes for “don’t lie on clauses, don’t drop incomplete refs, keep Profile as the dispute surface.” Not R06/clinical closure. Event/exposure **confirmed** clause conflict stays closed until published requirement consume-fields exist.
