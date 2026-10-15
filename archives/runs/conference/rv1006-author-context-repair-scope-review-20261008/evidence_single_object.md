Trellis SessionStart context loaded. Proceeding with the bounded read-only review (no Trellis task will be created — this is a read-only review pass, and plan mode already forbids writes).

Bash is denied in non-interactive mode — HEAD 21fce0f5 remains an unverified assumption (noted later). Continuing with targeted Grep/Read only.

Recovering the exact guard and merge semantics now.

# Bounded independent engineering review — source-insert link preservation (C03)

Scope: read-only, worktree `phase5-clinical-facts-profile`; 12 targeted Read/Grep ops (limit reached); no shell, no writes, no tests run. `HEAD=21fce0f5` **unverified** (shell denied in non-interactive mode); all line numbers are from the checked-out tree.

---

## A. Code observations (verified against source)

### A1. Producer: the projection drops the note-link mapping (matches owner observation)
- `ProtocolControlAgentInput` (`app/agents/protocol_control_deconstructor.py:331-350`) carries `owned_units / context_units / table_context_reading_bounds / known_official_targets / known_procedure_targets / known_workflow_stage_targets` — **no field for row/header→note-number links**.
- `from_batch` (`:370-389`) copies exactly those fields; it does not copy `table_footnote_context_links`, although the batch carries it and other readers consume it: `protocol_control_candidate_alignment.py:291,375` (`referenced_table_notes`) and `protocol_control_execution.py:2936` (deep batch planning).
- `build_protocol_control_agent_prompt` (`:2919-2990`) serializes the frozen input verbatim (`:2977`), strips only `member_source_span_ids` (`:2936-2938`), and trims target catalogs to display fields (`:2941-2963`). It never injects the note links.
- Consequence: the control Agent gets note paragraphs as flat excerpt context but not the explicit row→note binding, while the alignment reader (and the review-side helper below) do get it. This is a **projection omission**, not missing text.

### A2. Review side already has deterministic row-label machinery
- `_statement_schedule_label_sources` (`app/agents/protocol_control_source_interpretation.py:807-821`) derives `(span, text)` label sources from the owned unit's `table_context` plus same-table siblings via `schedule_row_values`.
- `_target_contains_row_label` (`:798-804`) requires every target excerpt to contain the label sources.
- `SourceTargetReviewItem` (`:824-841`) has decision vocabulary including `additional_requirement` (`:826-830`), optional `target_id` (`:831`), and object/scope/time excerpt fields (`:832-841`).
- `validate_source_target_review` (`:1679+`) enforces index coverage (`:1686-1690`), source-action membership (`:1706-1723`), and requires `unresolved_aspects` for non-covered decisions (`:1736-1739`). It has **no field that asserts "the baseline linked target is invalid"**.

### A3. Source-insert guard requires *every* old link, unconditionally
- `_restore_bounded_wire_repair` source-insert branch (`app/agents/protocol_control_deconstructor.py:4990-5052`):
  - `:4996` old candidates must be an exact immutable prefix, plus ≥1 new candidate.
  - `:5019-5041` for every authorized unit whose old disposition was `REQUIRED_PROCEDURE`/`OFFICIAL_ELIGIBILITY`, `expected_targets` = the old disposition's linked ids.
  - `:5042-5047` `actual_targets` = `cross_source_relations` of the **new** candidates.
  - `:5048-5051`: `expected_targets <= actual_targets` or `REPAIR_SCOPE_ESCAPE` (`"补入候选未保留原有官方或访视流程目标关系"`).
- No correctness precondition on the old link. A proposal that correctly drops a wrong old link is rejected; the wrong relation must be re-expressed on the new candidate. This reproduces the observed sequence: first proposal drops the bad link → `REPAIR_SCOPE_ESCAPE`; later proposal keeps it → insert passes.
- `_merge_source_candidate_insert` (`:6141-6222`) additionally requires new candidates to cover exactly the authorized unit set (`:6186`), and replaces the disposition's link fields with `null`/`[]` (`:6201-6207`), so links live on candidate relations afterwards.

### A4. Link *deletion* already has a bounded, sanctioned path — but not in source insert
- `build_protocol_control_repair_prompt` problem `PROCEDURE_AFFECTED_STAGE_MISMATCH` instructs: `"若无直接补充关系，删除该错误关系"` while `"保留有源独立候选及其真实判定节点"` (test `:8745-8751`). So the system already admits deleting a proven-wrong relation on the candidate-only path; the insert gate does not reuse that allowance.

### A5. Consumer identity/reuse
- Alignment: `NATIVE_TABLE_ALIGNMENT_CONTEXT_VERSION = "native-table-review-scope/v3"` (`protocol_control_candidate_alignment.py:21`); `native_review_scope` embeds `referenced_table_notes` only for units with `table_context` (`:281-292`, `:372-382`); proofs are application-owned (`:245-251`) and replay via `source_sha256 / candidate_sha256 / response_sha256` (`:431-449`). Content-addressed, replayable.
- Execution reuse: `_preflight_deep_source` (`execution:2886-2936`) binds reuse to frozen plan ids (`:2910-2912`), `_require_compatible_deep_source` (`:2896`), `_require_schedule_member_sources` (`:2906`).
- `_repair_material_matches` (`execution:3203-3242`) accepts repair receipts only for the current contract hash or two hardcoded legacy variants (`:3210-3217`) and then requires recorded `error_classes` disjoint from a per-variant affected set (`:3222-3230`, `:3242`). This is the codebase's **mini version-string whitelist**; also the source of the correct "don't reread unrelated observations" semantics.
- `_resumable_partial_deep_diagnostic` was **not found anywhere under `app/`** at this revision (1 negative grep). Closest existing concept: the `recompute_missing_diagnostic_steps` parameter (`execution:538,2891`) and `deep_reuse_plan` (`:547-554`). Owner's symbol name does not match this revision — treat as naming drift or a different slice.

### A6. Existing consumer tests that pin current semantics
`test_slice58c_control_deconstructor.py`: `:6316-6360` (mixed-source insert must re-express the procedure link; dropping it raises `REPAIR_SCOPE_ESCAPE`), `:8745-8751` (stage-mismatch prompt allows deletion), `:7587` (mixed official source keeps link when new requirement added), `:7659` (reuse unchanged validated target matches), `:10472` (rejects out-of-scope changes), `:10501` (one bounded candidate correction), `:6019` (addition enters bounded repair), `:7863` (restored review keeps additional requirement), `:5598`/`:7823` (repair/restore without rereading valid siblings), `:4235` (old receipts not relabeled as current).

---

## B. Answers

### Q1 — First causal defects, ordered
1. **Projection drop (P0).** `from_batch` omits the note-link mapping → the agent cannot bind row action ↔ note number; the wrong cross-row link is a downstream effect of that information asymmetry, layered on the guard. The fix is not "demand phase-II text": the note's phase-II paragraph must remain context, and the mapping is the machine-decided row↔note binding, not an obligation expansion. The prompt already forbids borrowing other sentences'/periods' obligations (`:2984-2988`).
2. **Additive-only insert gate (P0).** `:5048` converts any dropped link into `REPAIR_SCOPE_ESCAPE` with no subtractive path for a provenance-bound invalid link, even when the review side already rejected equivalence. Alternative already present: route link correction through a candidate-only deletion step (A4) before the insert, or derive `expected_targets` from the validated target set instead of the old disposition.
3. **Consumer asymmetry (P1).** The alignment reader enforces linked-note completeness while the control input never received the mapping. Not an independent defect once (1) is fixed, but it must not be weakened to compensate — an omission caused by the guard must be fixed at the guard, not by relaxing alignment.

### Q2 — Smallest fix, evidence sufficiency
- **Producer (smallest):** add the batch's `table_footnote_context_links` to `ProtocolControlAgentInput` and copy it in `from_batch` (reusing the existing field name/shape; refs at alignment `:291`, execution `:2936`). The prompt dump then carries it automatically; add one explicit prompt sentence that the mapping is host-frozen context, never an obligation expansion, and that only the frozen-node/phase paragraph is the current requirement. No new note blob serialization: reference existing per-paragraph span structure.
- **Guard (smallest, preserving gate strength):** keep `expected_targets <= actual_targets` as the default; subtract only links the frozen review explicitly invalidated, bound to `(unit_id, external_target_kind, external_target_id)`. Concretely, a validated set `invalidated_links` computed from frozen review + baseline, then `expected_targets -= invalidated_links`. Unexplained drops keep failing with the `:5050` message.
- **Is existing structured evidence sufficient for link-only correction before insertion?** Not yet. `SourceTargetReviewItem` has the excerpt fields (`:837-838`) and `additional_requirement` decisions, and `validate_source_target_review` can check excerpt membership — but **no field asserts "this specific baseline link is invalid"**, and `additional_requirement` means "the statement adds something beyond the target", not "the old target is wrong". So either the correction runs through an explicit reviewer determination, or the gate stays. **Missing evidence contract to add** (minimal): `{old_target_kind, old_target_id, mismatch_basis ∈ {object, scope, stage}, source_object_excerpt, target_object_excerpt, source/unit span ids}`, deterministically validated (excerpts must occur in the frozen unit/target sources; both sides present; review item index valid) — then subtraction is auditable. Do **not** infer drops from a decision value alone or from free-text errors ("不同对象").
- **Non-regression counterexamples that must survive:** same sentence with covered procedure + independent new requirement (`:6316`, `:7587`) — link must be kept; outside-table reference to another physical source — different spans alone never justify subtraction, so deletion criteria must be object/scope-bound, never span/source-id-based.
- **Consumer:** alignment and insert-coverage rules unchanged; the corrected case should pass with surviving links carrying their note details.

### Q3 — Identity/reuse
- Base projection change must not claim old requests used it: the input already carries `schema_version` (`:334`). Adding a field changes projection content; reuse must key on the **stored frozen payload identity** (already the pattern in `_preflight_deep_source`), not on any accepted-version list.
- Do not extend `_repair_material_matches`'s hardcoded legacy set (`:3212-3217`) — that is exactly the per-request version whitelist to avoid. Its error-class disjointness check (`:3242`) is already the right "don't force rereading successful observations" semantics; keep it scoped as is.
- Unused recovery/unused new projection must not invalidate the 16 completed units by default: their results remain keyed to their own frozen inputs; affected scope = completed units that consumed table/note context. Whether the frozen payloads show which units did is a **data check not run here** (uncertainty U3).
- No retrospective rehash: alignment proofs and repair receipts already hash content; no new cache or hash layer is needed.

### Q4 — Sufficiency of bounded projection / branch status
- Bounded projection alone is **necessary but not sufficient**: the failing unit's baseline wire already contains the wrong link, so an insert-only path still re-expresses it or fails; the corrective subtraction contract (Q2) is required. With projection + contract + unchanged additive default, local correction is sufficient and unit-scoped.
- The branch may therefore stay failed for that unit until (a) the reviewer contract and guard subtraction exist and (b) consumer tests pass; independent delivery work can proceed in parallel because the change is confined to projection/schema/reviewer/guard, not shared clinical rules. Whole-protocol rerun is not the default; resuming from the failed step with unaffected units untouched follows from the prefix-immutability design (`:4996`) and per-step checkpoints.
- One diagnostic is not proof either remedy closes the task — see required tests below.

---

## C. Recommended minimal changes + consumer tests

1. `protocol_control_deconstructor.py`: extend `ProtocolControlAgentInput` + `from_batch` (`:331-389`) with the existing note-link mapping; bump `CONTROL_AGENT_INPUT_VERSION`; one prompt sentence (host-frozen mapping; phase/node-scoped obligation selection).
2. `protocol_control_deconstructor.py:5019-5051`: subtract review-validated invalid links from `expected_targets`; no other guard relaxation.
3. `protocol_control_source_interpretation.py:824-841, :1679+`: add the explicit link-invalid determination + deterministic validation (or reuse an existing stage-mismatch decision if one already carries target identity — not verified).
4. Tests to add: projection carries mapping for a table-linked unit and does not import phase-II obligations when phase III is selected; insert succeeds when the review invalidated the old link; insert still fails `REPAIR_SCOPE_ESCAPE` when a link is dropped without the determination; mixed-source legitimate link survives. Reuse `:6316`, `:7587`, `:10472`, `:10501`, `:6019`, `:8745`, `:5598`, `:4235`.

## D. Unexecuted checks / uncertainties
- HEAD 21fce0f5 unverified (shell denied); results are valid only for the checked-out worktree.
- Did not read the repair-prompt body `:3054+` or `_repair_problem_guidance:2303`; the gate at `:5048` independently explains the observed failure, but prompt text may already mention preserved links.
- Did not read `_require_compatible_deep_source`; whether deep-source reuse hashes the *projection* or only plan IDs is an inference (U3 above).
- `_resumable_partial_deep_diagnostic` absent from `app/` at this revision (negative grep) — owner's naming may not match this tree.
- `table_footnote_context_links` definition/type on the batch not read (only its use sites); the recommendation reuses the field by name.
- Failure reproduction (terminal run) not re-run; no clinical determination made, per assignment.

**Separation:** Sections A and the `:line` claims are code observations; sections B–C are recommendations; D lists checks not executed.
