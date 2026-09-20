I’ll re-read the current integration against those six source facts and only keep findings that still hold after reconciliation.The first batch didn’t land because of a tool-name mismatch. I’ll retry those reads with the standard file reader.v14, date-pair admission, and the publication audit path look different from the first pass. I’ll trace qualification accounting and proposition reconstruction next.Reconciled: v14 is this increment’s consumer id, date propositions cannot enter the job, and predicate audits are published. Remaining issues are fail-closed limitations, not a v15 bump.# Conference Output: r05-semantic-ordering-review-20260915 - evidence_single_object

## Output

**Fallback / capability.** Same-session follow-up as declared `pi` fallback `cursor` / `cursor-grok-4.6`, not `grok-build` / `grok-4.6`. Read-only source inspection only. No compile, imports, tests, models, DB, or browser. Live-method inventory is outside this tree and is not independently verified here.

**Source-review verdict (current construction only): PASS, with remaining fail-closed limitations.** Prior FAIL on extra consumer bump, date-relation injection, missing predicate audit, and “drop rejected content pairs” is **withdrawn**. This is not clinical, regulatory, or product-adoption authority.

### Evidence

**E1. Consumer seal is the current constant, not a prior live algorithm.** `QUALIFIED_BINDING_CONSUMER_ALGORITHM` is `qualified-binding-selection-consumer/v14`. `_validate_authorization` requires **exact equality** with that constant (`qualified_binding_selection.py` 165–166). Material write uses the same constant (726–727). Historical `Literal` members still parse old blobs; they cannot execute this consumer. Evaluator is `component-review/v20`. Control spec default is `control-atom-evaluation/v3`; wire `phase5/control-agent-wire/v9`; prompt `phase5/control-agent-prompt/v2.5`. No extra bump is justified from source.

**E2. Date propositions cannot enter the job.** `load_proposition_evidence_input` keeps only `value` / `assertion_basis` pairs whose `assertion_basis.locator_id` equals the pair locator; others go to `skipped_pairs` as `bound_assertion_source_missing` or `declared_source_attribute_mismatch` (`proposition_evidence_input.py` 49–58). Lane validation repeats the same gate (`proposition_evidence.py` 22–25: “不接受日期作为命题依据”). Receipt rebuild calls `load_proposition_evidence_input` and requires byte equality with the stored payload (`proposition_evidence_receipts.py` 35–44, 92). `verify_qualified_proposition_evidence` then requires every evidence pair to match a qualification pair. Helper still rejects a foreign non-content relation as `semantic_evidence_unverified` rather than dropping it (`semantic_observation_selection.py` 129–135).

**E3. Predicate ordering is published and rechecked.** `frozen_review_publication.py` 147–157 copies sealed `identity_outcomes[].observation_ordering` onto `PredicateObservation`. `review_history_service.py` 405–416 requires that audit to match the predicate policy hash and current fact ids. Control storage forbids used facts in `not_selected` (`review_control_repository.py` 97–103). Assessment candidates still cannot supply this audit (`review.py` 266–267). Material already stores `proposition_evidence` job refs plus pair-level gaps with `locator_id` (`qualified_binding_selection.py` 703–711). Fact-level `OrderedObservationAudit.not_selected` is locator-capable via frozen facts. Copying full `not_selected_relations` into every material is not required for audit.

**E4. Candidate accounting and qualification pairs are different layers.** Comparison accounting is per fact over the read universe (`candidate_fact_accounting.py` 63–78; statuses in `binding_candidate_comparison.py` 10–20). Qualification pairs are built only from comparison **candidate** rows; “Exclusion/uncertainty rows never become pairs” (`binding_qualification_support.py` 719–721, 655–706). `agreed_noncorrespondence` therefore has no pair to reject. `candidates_in_both_lanes` facts **can** later fail pair qualification and appear in `rejected_pairs` while remaining in `summary.pair_records`. Helper `source_records` is those pair records, not `usable` only (`qualified_binding_selection.py` 340). Coverage requires every source **content** pair to have a verified relation before date choice (`semantic_observation_selection.py` 121–143). `observation_scope_reasons` still requires accounting fact_ids == full frozen `facts` and `candidates_in_both_lanes == operands` (`ordered_observation_selection.py` 20–41).

**E5. Control zero-relation branch now calls declared ordering.** Empty relations set `semantic_evidence_unverified` and, if `selection` is present, call `_semantic_ordering` (`qualified_binding_selection.py` 606–616). Non-empty relations still overwrite arithmetic leftovers. Helper now tests incomplete coverage **before** empty copies (140–143). Predicate with `selection` already called the helper even when `relations` is empty (531–539). Control v3 explicit validation requires `observation_policy` for every mode, or unresolved (`control_evaluation_spec.py` 100–102). Prompt now says “所有求值模式均须observation_policy” (`protocol_control_deconstructor.py` 1240–1248).

**E6. Date/tie/window behavior is still the deterministic selector.** Same-day exact bounds → `observation_tie_unresolved`; overlapping partial bounds → `observation_order_ambiguous_partial_date` (95–104). `window_order` None/`unresolved` or mismatch with constraint presence → `observation_window_policy_unverified` (56–59). `within_window` drops out-of-window before ranking; `before_window_check` ranks first and does not fall back to an older in-window fact (88–110). Missing bounds → `ordering_date_missing`. Content candidates without a qualified `date_range` pair, including when the protocol has no time constraint → `known_date_unqualified` (151–154). Selector `time_purpose` accepts only `event_membership` and `source_validity` (80–82). Clinical adoption flags remain `False` on selection material.

**E7. Non-selected relations are unused, not false unresolved.** After selection, excluded pair_ids are omitted from `proposition_relations` and are **not** appended as `identity_selection_unresolved` when the fact is in `observation_ordering.not_selected` (692–714). Downstream calculation only sees remaining selected pairs.

### Inference

**I1. I4/U1 extra v15 bump — withdrawn.** In this construction, v14 **is** the semantic-ordering consumer id. `_validate_authorization` will not run a different constant. Historical literals are parse-only. Live-method absence is an owner operational claim, not something this tree can prove; it is not a reason to mint v15.

**I2. E4/I2 date-relation false reject — withdrawn as a live path.** Input, lane validator, and receipt rebuild cannot inject `date_range` propositions. Helper fail-closed on a foreign non-content row is defense in depth, not a normal rejection of a complete content set.

**I3. E9/I5 missing predicate audit — withdrawn.** Publication, history, and (for controls) storage already bind `observation_ordering`. Pair-level proposition evidence remains on the frozen job/material.

**I4. Rejected content pairs must block latest/earliest, not be dropped.** A `candidates_in_both_lanes` fact whose value/assertion pair later fails qualification is still in `source_content_pairs`. Missing relation → `single_observation_relations_incomplete`. A date-only dual-lane candidate stays in accounting candidates and, if not an operand, fails `observation_operand_set_unverified`. That is conservative qualification, not a false exclusion that authorizes an older readable observation. `agreed_noncorrespondence` never produced a pair, so it cannot appear as a rejected pair in the summary.

**I5. Empty-relation control no longer claims arithmetic.** Declared `selection` now reaches the helper; helper prefers incomplete over empty-unverified when content pairs exist. Missing v3 policy fails explicit deconstruction/validation rather than silently omitting latest.

**I6. Remaining issues are fail-closed limitations, not false acceptance of a non-governing observation.** No source path was found that would adopt an older qualified fact while a newer dual-lane content candidate is merely unreadably qualified, or that would invent a date, or that would treat same-day/partial order as decided.

### Recommendation

**R1. Do not bump v14 for this increment.** Keep `_validate_authorization` on the current constant. Mint a new consumer id only if ranking/coverage rules change after this construction.

**R2. Keep exact content-pair coverage.** Do not add a path that drops rejected `value`/`assertion_basis` pairs for `candidates_in_both_lanes` facts in order to pick an older dated fact.

**R3. Do not add staged tests in this change set** (user deferral). Construction-only.

**R4. Optional later (not blocking this construction):** if a protocol needs `time_purpose=interval_condition` plus latest/earliest, extend the selector’s allowed purposes explicitly; today it is `observation_window_policy_unverified`. If official IN/EX latest/earliest must be captured at deconstruction, that is a separate official-agent gap (control v3 already requires policy).

**R5. Optional reason-code cleanup:** control empty relations with `observation_policy is None` currently stay on `semantic_evidence_unverified` only; adding `observation_selection_unverified` would match the nonempty-relation branch. Still unresolved, not adoptable.

### Uncertainty

**U1.** Authorized live methods / in-force v14 authorizations: **UNVERIFIED** from this tree. Owner states none exist. Source only proves new consumption requires current v14.

**U2.** No compile or behavioral run. Line claims are from current file text after the owner’s integration edits.

**U3.** Batched predicate accounting concatenated to a unique full-fact cover is **UNVERIFIED** at runtime. Fail-closed (`candidate_enumeration_incomplete`) if rows duplicate or miss facts; false acceptance is unlikely.

**U4.** Official IN/EX agent (`protocol_deconstructor`) was not shown to emit `observation_policy` in this packet. Missing official latest stays `observation_selection_unverified` at consumption. Capture completeness **UNVERIFIED** beyond control v3.

### Resolved / rejected / remaining

| Id | Status | Definition |
|---|---|---|
| Extra v15 bump (old I4) | **Rejected** | v14 is this increment’s algorithm; exact-constant gate |
| Date-proposition false reject (old E4/I2) | **Resolved** | Dates skipped at input, validator, and receipt rebuild |
| Missing predicate `observation_ordering` (old E9/I5) | **Resolved** | Copied in publication; history/storage recheck |
| Copy `not_selected_relations` into material | **Rejected as required** | Job ref + pair locator + fact-level audit suffice |
| Drop rejected content pairs to rank remaining | **Rejected** | Would hide an unreadable latest dual-lane candidate |
| Control empty-relation arithmetic leftover | **Resolved** | Helper/coverage reasons; no `*_not_direct_arithmetic` |
| Control v3 policy required | **Resolved** | Validation + prompt |
| Helper empty vs incomplete order | **Resolved** | Incomplete first |
| Same-day / partial ties | **Remaining, fail-closed** | Unresolved; no invented order |
| Unknown / unqualified dates | **Remaining, fail-closed** | `ordering_date_missing` / `known_date_unqualified` even without a time constraint |
| `interval_condition` + `selection` | **Remaining, fail-closed** | Selector allows only `event_membership` \| `source_validity` |
| Window membership uses `lower_bound` only | **Remaining, shared with deterministic** | Dominance uses `[lower, upper]`; partial window → UNKNOWN via `evaluate_time_constraint` |
| Official IN/EX policy optional at deconstruction | **Remaining capture gap, fail-closed at consume** | Not a false-accept path |
| Empty-relation missing-policy reason code | **Remaining cosmetic** | Still unresolved |
| Clinical adoption | **Out of scope** | Flags stay false; user deferred tests |

### Objections, alternatives, decision points, bounded questions

**Objection to the withdrawn “usable-only candidates” advice.** Treating rejected qualification of a dual-lane content pair as “accounted noncorrespondence” would let an older readable observation govern. Qualification failure is not proposal-time `agreed_noncorrespondence`. Current exact coverage is the correct conservatism for “true latest may be unreadable.”

**Safe provisional path.** Accept this construction as source-bound selection accounting. Do not authorize clinical use. Do not drop rejected content pairs. Do not bump v14 unless behavior changes.

**Decision points for Codex**

1. Treat remaining `interval_condition`+selection as an accepted fail-closed limitation for this increment? **Recommend yes.**
2. Official IN/EX latest capture: later deconstructor work, not this consumer? **Recommend yes.**
3. Empty-relation reason-code alignment: optional, not blocking.

**Bounded questions** (only if Codex needs a different product rule)

1. Should a dual-lane fact with a rejected **value** and a usable **date_range** remain unresolved (current), or may latest among remaining **content-qualified** facts proceed? Current code: unresolved. Changing that is a new consumer version.
2. Confirm no in-force authorization already hashes to v14 from a **different** ranking rule. If that operational claim is wrong, that is an authorization-inventory problem, not a source bump inside this increment.

**Most important remaining defect/uncertainty.** Not a false-accept: `select_ordered_observation` will not rank under `interval_condition`, and official IN/EX may omit `observation_policy` so “最近一次” never reaches the helper. Both stay unresolved. No source path was found that adopts a non-governing observation or an invented date.
