Delegated conference pass as `evidence_single_object` (cursor/cursor-grok-4.6 fallback). I’ll start from the assigned context and plan, then inspect only the listed sources for semantic latest/earliest integration, candidate accounting, and version-bound adoption.Context is loaded. Next I’ll inspect the frozen source files for latest/earliest selection, candidate accounting, and version-bound adoption.The first pass was truncated. I’ll read the remaining selector, integration, and version-bound call sites in full.Grep didn’t hit the worktree paths, so I’ll read the integration files directly and search from the authorized workspace.The helper exists; I’ll now check whether callers actually wire it, including ordering, versions, and proposition evidence.Integration is present. I’ll now check accounting, version literals, deconstructor schema, and whether non-selected relations stay auditable.Workspace search isn’t indexing these files, so I’ll run a direct read-only search in the authorized tree.# Conference Output: r05-semantic-ordering-review-20260915 - evidence_single_object

## Output

**Fallback / capability.** This pass ran as the declared `pi` fallback `cursor` / `cursor-grok-4.6`, not the primary `grok-build` / `grok-4.6` route. Read-only source inspection only: no compile, runtime, staged tests, browser, or production writes. Workspace `Grep` did not index this worktree; evidence is from direct reads plus `rg` in `.`. Git history for the consumer/helper files was empty here. Execution worker report was not supplied and was not used.

**Source-review verdict: FAIL.** Semantic latest/earliest is wired, but the candidate universe, relation filter, and version seal do not match the deterministic selector or the stated accounting rule. This is a source-integration verdict, not product/clinical/regulatory acceptance.

### Evidence

**E1. Helper exists and delegates date choice.** `app/services/semantic_observation_selection.py` copies inputs, requires `policy.mode == "single"` with `latest`/`earliest` and `ordering_attribute == "date_range"`, requires `review_context`, requires a qualified `date_range` for every relation fact even without a time window (lines 151–154), then calls `select_ordered_observation` (161–171). Same-day/partial dominance stays in the deterministic selector (`ordered_observation_selection.py` 95–104): unique strict bound dominance, else `observation_tie_unresolved` or `observation_order_ambiguous_partial_date`. Window order is explicit (`57–59`): `None`/`unresolved` fails; no constraint iff `window_order == "not_applicable"`; `within_window` drops out-of-window before ranking; `before_window_check` ranks first and does not fall back to an older in-window fact.

**E2. Integration calls the helper on both families when `policy.selection` is set.** Predicate path: `qualified_binding_selection.py` 518–539. Control path: 604–627. Non-selected relations are omitted from `proposition_relations` and skipped as gaps when listed on `observation_ordering.not_selected` (681–703). Control audits are forwarded into `frozen_review_calculation.py` 196–198 / 307 and `project_control_review_outcomes`. Storage rejects used facts that intersect `not_selected` (`review_control_repository.py` 97–103).

**E3. Coverage input is all identity pair records, not qualified candidates.** `_semantic_ordering` (330–343) passes `source_records=[item for item in records if item.identity_sha256 == identity]` where `records = list(summary.pair_records)` (419). The helper then requires every `value`/`assertion_basis` pair_id to equal verified relation pair_ids (121–143) before date selection. Rejected pairs remain in `summary.pair_records` and in `rejected_pairs` (469–488) but have no verified relation.

**E4. Relations passed into the helper are not content-filtered.** Both families pass `relations = [item for item in proposition_relations if item["identity_sha256"] == identity]` (520, 605). `select_qualified_relations` emits agreed rows for every evidence pair, including `date_range` (`qualified_proposition_evidence.py` 65–101). The helper treats every relation as a content pair and fails `semantic_evidence_unverified` if `pair_id` is not in the content `source_by_pair` map (129–135).

**E5. Control semantic with zero relations never reaches the helper.** `_select_with_ordering` returns `_select_facts_for_identity` for non-deterministic specs (288–289), which yields `determination_mode_{mode}_not_direct_arithmetic` (248–249). The semantic overwrite is gated on `if relations:` (604–606). Empty relations keep the arithmetic reason. Predicate still enters the semantic block when `semantic_proposition` is set (518–523) and will call the helper if `selection` is present (531–537).

**E6. Empty relation copies hide incomplete coverage.** Helper order (140–143): empty `relation_copies` → `semantic_evidence_unverified`; only then `single_observation_relations_incomplete`. A nonempty source content set with zero relations never surfaces the incomplete reason.

**E7. Control vs predicate completeness without `selection` differs.** Predicate no-selection single uses all source content pairs (524–541). Control no-selection single uses `usable` content pairs only (628–632).

**E8. Helper `not_selected_relations` are unused.** `SemanticObservationSelection.not_selected_relations` is built (174–178, 212) and never copied into material. Only `OrderedObservationAudit.not_selected` (`fact_id` + reason) survives.

**E9. Predicate ordering audit is not projected into frozen component observations.** `calculate_frozen_review` passes control audits only. `calculate_component_review` has no `observation_ordering` argument. `review_history_service.py` 405–416 still expects `PredicateObservation.observation_ordering` when a policy has `selection`. Assessment candidates are forbidden from supplying that audit (`review.py` 266–267).

**E10. Version seal is unchanged.** `QUALIFIED_BINDING_CONSUMER_ALGORITHM` remains `qualified-binding-selection-consumer/v14`; material `qualified-binding-selection/v5`; proposition consumer `qualified-proposition-evidence/v6`; evaluator `component-review/v20`; control experiment `v10`; control-review-outcome `v3`. Historical literals still accept older consumer versions. Current algorithm is what `_validate_authorization` binds (165–166). Frozen review still rejects evaluator/rule-set mismatch (164–168) and review-context hash drift (425–426, 779–783). Semantic control `selection` is refused on non-v3 specs (`control_evaluation_spec.py` 97–99). Old selection versions cannot receive `observation_ordering` (`qualified_binding_selection.py` 215–218).

**E11. Deconstructor prompt/schema.** `CONTROL_AGENT_PROMPT_VERSION` is `phase5/control-agent-prompt/v2.5`; wire `phase5/control-agent-wire/v9`. Schema injects `ObservationOrdering.provider_json_schema()` (1156–1158), which requires `window_order`. Prompt says deterministic specs must have `observation_policy`, then that any mode may add `latest`/`earliest` under `single` with explicit `window_order` (1240–1248). `validate_control_atom_evaluation(..., require_explicit=True)` requires a policy only for deterministic specs (100–101), not semantic/investigator_judgment.

**E12. Accounting vs operands.** Identity accounting rows include every fact in the candidate read (`candidate_fact_accounting.py` 63–78; comparison statuses in `binding_candidate_comparison.py` 10–20). `observation_scope_reasons` requires accounting fact_ids == the full `facts` dict passed in, candidates = `candidates_in_both_lanes` == operands, and any other status → `observation_scope_unverified`. Predicate candidate reads may be batched (`predicate_binding_candidates.py` 186–187, 231–233); control reads use the full fact universe (145–147). Concatenated multi-batch rows for one identity can duplicate fact_ids and trip `candidate_enumeration_incomplete` (`ordered_observation_selection.py` 26–28).

**E13. Non-use of excluded relations in calculation.** After filter, `evaluate_control_layers_experiment` and `calculate_predicate_propositions` only see remaining selected pairs. Excluded facts are not labeled `identity_selection_unresolved`. `combine_observations` still requires `scope_verified` for semantic `single` (`proposition_observations.py` 12–18). Control `scope_verified` uses lane `scope_correspondence`, not `scope_candidates_complete` (`control_calculation_experiment.py` 270–276). Clinical adoption flags stay `False` on selection material (178–180, 753–755).

### Inference

**I1. Highest-impact defect: candidate universe is not the same as deterministic latest/earliest.** Deterministic selection ranks *usable qualified operands* and keeps non-candidates as accounting (`agreed_noncorrespondence` is not an operand; other disagreements fail closed). Semantic selection demands a verified relation for *every supplied content pair*, including pairs already rejected by qualification. One failed object/attribute match among several otherwise qualified observations blocks date choice (`single_observation_relations_incomplete` or, if no relations remain, `semantic_evidence_unverified`). That is not “accounted then qualified then ordered”; it treats rejected pairs as missing relations. It also contradicts “do not insist on unverifiable completeness from enumerated data” and “latest/earliest applies to deterministic and semantic.”

**I2. Date_range (and any non-content) agreed relations are a second false-rejection path.** If proposition evidence agrees on a date pair for the same identity, the helper cannot bind that row to `value`/`assertion_basis` and fails `semantic_evidence_unverified` even when content coverage is complete. Integration mutates `scope_candidates_complete` on the unfiltered list (522–527, 609–613) before the helper independently recomputes the same flag.

**I3. Control empty-relation path is a valid-input miss.** An explicit `selection` on a semantic/investigator atom with no verified content relations should still run the helper and return coverage/selection reasons. Leaving `determination_mode_semantic_not_direct_arithmetic` conceals that latest/earliest was declared and never applied.

**I4. Version-bound adoption is not sealed for this behavior.** If v14 already authorized deterministic-only consumption, semantic ranking under the same consumer id lets old authorizations run a new algorithm. Source here has no v15/`v6` material bump. Historical version gates prevent *backfilling fields onto old blobs*, which is necessary but not sufficient: they do not prevent *new code* from executing under an old algorithm id.

**I5. Official IN/EX audit trail is incomplete relative to controls.** Control latest/earliest can appear on `ControlReviewOutcome` and is checked at save. Predicate latest/earliest sits on qualification `identity_outcomes` only. History/API already know how to show `PredicateObservation.observation_ordering`, but frozen review never fills it. Non-selected semantic rows are not retained as frozen evidence on the selection material; only fact-level exclusion reasons are.

**I6. Deconstructor will under-declare semantic latest/earliest.** Prompt “必须” for `observation_policy` is deterministic-only; explicit validation matches that. Protocol text that says “最近一次” on a semantic atom can hydrate with `observation_policy is None`, after which neither helper nor deterministic selector runs. `window_order` is required in the provider schema, which is good; missing policy is the hole.

**I7. Fail-closed pieces that should stay.** No date invention in ordering; partial/same-day ties unresolved; `before_window_check` does not silently pick an older valid record; `source_validity` expired latest stays unresolved; non-selected relations are not turned into false gaps; clinical adoption cannot be flipped true by this consumer; old control specs cannot grow semantic selection; review-context hash and evaluator version still bind the frozen review.

### Recommendation

**R1. Align the semantic candidate set with deterministic accounting (must-fix).** Before `select_semantic_ordered_observation`:

- Content pairs in scope = identity pairs whose fact is `candidates_in_both_lanes` *or* that remain in `usable_records` with `value`/`assertion_basis`.
- Qualification-rejected / `agreed_noncorrespondence` / uncertain facts stay in `rejected_pairs` and accounting; they must not be “missing relations.”
- Require verified content relations for *that* candidate pair set, then delegate dates.

**R2. Filter helper `relations` to content attributes** (`value`, `assertion_basis`). Keep date relations for time-operand pair_id attachment only (already done after selection at 542–548 / 633–641). Do not send `date_range` rows into content-pair identity checks.

**R3. Always invoke `_semantic_ordering` when `policy.selection` is declared**, including zero relations and control semantic/investigator modes. Drop the `if relations:` gate. Let the helper own empty/incomplete reasons.

**R4. Reorder helper gates:** if content candidates exist and relation coverage is incomplete, return `single_observation_relations_incomplete` even when `relations` is empty. Reserve `semantic_evidence_unverified` for identity/pair mismatches and empty *candidate* sets.

**R5. Bump the consumer algorithm** (v14 → v15 at minimum) and the authorization `Literal` default. Do not let existing v14 authorizations execute the new ranking. Keep old material versions unable to grow new fields.

**R6. Persist audit, not use, of non-governing relations.** Copy `not_selected_relations` (or pair_ids + reason) onto the selection material; keep them out of `proposition_relations` and out of gaps. Project predicate `observation_ordering` onto frozen `PredicateObservation` the same way controls already do, so history checks have a real object.

**R7. Prompt/validation:** require `observation_policy` on semantic/investigator specs when source latest/earliest is claimed; if the source is unclear, `mode=unresolved` / `window_order=unresolved`, never omit. Keep “确定性规格另须…” from implying semantic specs need no policy.

**R8. Do not add staged tests in this change set.** Source-only follow-up: walk one identity with mixed usable + rejected content pairs, one with extra date relations, one batched predicate accounting concatenation, and confirm v15 rejects v14 authorizations.

### Uncertainty

**U1.** Whether `qualified-binding-selection-consumer/v14` was minted for this semantic wiring is **UNVERIFIED** in this worktree (no usable git history). If Codex already reserved v14 for this helper, R5 reduces to “confirm and document”; if v14 shipped deterministic-only, R5 is mandatory.

**U2.** Runtime frequency of date_range rows in `proposition_relations` is **UNVERIFIED** (no execution). The type-level path exists; whether current proposition jobs emit agreed date rows is unknown.

**U3.** Batched predicate accounting concatenated to a unique full-fact cover is **UNVERIFIED**. Fail-closed (`candidate_enumeration_incomplete`) is likely if batches overlap; false acceptance is unlikely.

**U4.** `interval_condition` + `selection` is rejected as `observation_window_policy_unverified`. Whether any published spec uses that pair is unknown; fail-closed is consistent with “no guessing.”

**U5.** No compile, import, or behavioral run was performed. Line-level claims are from source text only.

**U6.** Other conference roles were not in the read set and are not merged here.

### Objections, alternatives, decision points, bounded questions

**Objection.** Treating “all supplied pairs must be content-qualified before date choice” as “every pair_record including rejected ones must have an entails/contradicts relation” makes semantic latest/earliest strictly harder than deterministic latest/earliest and can make it impossible whenever any content pair fails qualification. That is the wrong conservatism: it converts a qualification rejection into a missing-observation problem.

**Proposed default if Codex does not answer.** Implement R1–R5 as the safe path: candidate pairs = usable content pairs ∪ `candidates_in_both_lanes` content pairs; rejected pairs remain audit; bump consumer to v15; do not adopt results under v14.

**Decision points for Codex**

1. Candidate universe: usable/accounted content pairs only, **or** literally every `pair_record` (current helper)?
2. Was v14 already the semantic-ordering algorithm id, or must it bump?
3. Should predicate `observation_ordering` be projected in this integration, or is qualification material the sole audit store until a later owner task?
4. Should `not_selected_relations` be serialized, or is fact-level `OrderedObservationAudit.not_selected` enough given the proposition-evidence job remains frozen?

**Bounded questions**

1. For an identity with two qualified value pairs and one `object_match` rejection, should latest/earliest run on the two, or stay unresolved? This decides R1 vs keeping E3.
2. Confirm whether any in-force authorization already has `consumer_algorithm_version=qualified-binding-selection-consumer/v14`. If yes, changing ranking without v15 authorizes old results.
3. Are date_range pairs in-scope for pair-local proposition relations on semantic atoms? If yes, R2 is required; if no, still filter defensively.

**Safe provisional path.** Do not treat current semantic latest/earliest as adoptable. Keep non-selected relations unused (already true). Do not run staged tests. Owner integration should not be accepted until candidate accounting matches the deterministic selector and the consumer version uniquely names this behavior.
