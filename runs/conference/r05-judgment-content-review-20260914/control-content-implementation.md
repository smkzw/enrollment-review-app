I’ll inspect the implemented control written-content path and adjacent consumers against the stated version/receipt rules, then report only source-proven defects.# C03 source review: control written-content (implemented)

Source only. No clinical acceptance. Runtime verification deferred.

**What landed (not defects):** Control linker uses verified frozen candidate + context (`control_judgment_fact_linkage.py:23-30`), same assertion index (`judgment_fact_linkage.py:43-59` via `evidence_input`), published `requirement_id` + `episode.workflow_stage_id` + `atom_refs` (`linkage.py:38-46`). Predicate input stays `judgment-content-input/v1`; control `…/control-v1` (`judgment_content_input.py:65`). Coverage `atom_refs` forced to lists (`62`). Same `JOB_TYPE`/prompt; empty pairs summary-only (`judgment_content_job.py:99-107`). Workflow `v2` adds `control_judgment_content`; `v1` readable and not required (`prepared_review_workflow.py:26-32,72,238-239,251-252,291-295`). Auth `v3` allows both families; `v2` predicate-only (`qualified_binding_selection.py:66-70`). Consumer `v6` + content `v2` (`contracts/qualified_binding_selection.py:23`; `qualified_judgment_content.py:7,22`). `verified_judgment_requirements` only if `family=="predicate"` (`qualified_binding_selection.py:504-508`). Publication maps both jobs (`prepared_review_publication.py:43-48`). Condition keys `layer/group_index/atom_index/protocol_control_id` exist (`binding_qualification_support.py:236-243`); `ReviewEpisode.workflow_stage_id` exists (`review.py:116`).

---

**P1 — Control `content_supported` still clears a professional-gap reason at pair admission**

`pair_direct_selection_rejection_reasons` is family-blind: `written_content_verified` adds `professional_judgment_applicability_unverified` to `resolved_checks` (`qualified_binding_selection.py:76-77,349-355`). Identity selection correctly does **not** pass `written_content_verified` for control (`449-450`) and still returns `determination_mode_investigator_judgment_not_direct_arithmetic` (`231-232`). That blocks PJ-atom **truth**. It does **not** stop a dual-agreed **deterministic** control pair whose only leftover reason was that professional check from becoming usable.

Minimal fix: resolve that check only for `family=="predicate"` (or `written_content_verified=False` on control records). Keep recording `content_supported_pair_ids`.

---

**P2 — Empty `atom_refs` still labeled `unique_source_match`**

If the published requirement exists at this node but `atom_refs` is empty, matches are still indexed and status can be `unique_source_match` (`control_judgment_fact_linkage.py:44-64`). Pairing then fails (`judgment_content_input.py:44-53`) — fail-closed, not false accept — but coverage overclaims “unique source” without explicit refs.

Minimal fix: if `not refs`, do not unique-match (leave unassigned / no matches). Do not invent a singleton ref.

---

**P2 — `workflow_stage_id is None` yields all-outside-scope (fail-closed)**

Filter is `item.workflow_stage_id == source.evidence_input.episode.workflow_stage_id` (`linkage.py:40`). Requirement ids are always non-empty mapped targets (`control_evidence_requirements.py:69-86`); episode field may be omitted (`review.py:116,138-139`). Prepared v2 context normally requires the stage (`review_context_v2.py:183`). If null, every control search is `requirement_outside_binding_scope` → summary-only, no model. Not false accept; control writing never links.

Minimal fix: treat missing episode stage as outside scope explicitly (current outcome) or refuse enqueue of control content when the node has no stage.

---

**Not defects:** v1 workflows publish without `control_judgment_content` (`publication.py:47-48` + expected set). Predicate v1 coverage still walks all searches (control rows already `requirement_outside_binding_scope`). Auth constructor defaults `v3` (`qualified_review_command.py:130-138`) — old evals must be re-issued at consumer v6/content v2 by design. Frontend distinguishes two `judgment_content` rows via `candidateJobId` (`PreparedReviewPanel.tsx:19-20`).

**Deferred:** no import/runtime of linkage rebuild, empty-pair job, or pair-admission with control `content_supported`.
