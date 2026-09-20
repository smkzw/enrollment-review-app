# Codex Conference Review: r05-control-expectation-scope-20260914

Date: 2026-09-14

## Verdict

Revise design before extending the requirement pipeline; advisory pass accepted as source-based review, not product or clinical acceptance.

## Boundary Compliance

Read-only source pass, 42 tool calls, no application changes, tests or product/DB calls reported. Runner terminal 0; no fallback. Owner keeps final integration.

## Participant Outputs Reviewed

runs/conference/r05-control-expectation-scope-20260914/evidence_single_object.md read in full. Runtime zcode/zcode/GLM-5.3 max, identity verified, session sess_627a5c35-48a6-46c1-b8b6-ac8be633fb1f; stdout receipt SHA binding retained.

## Conference Panel Review

F1/F2/F3/F5/F6 identify real contract constraints: one requirement per node, ambiguous minimum-evidence node identity, two-origin storage, conditional blocking, and non-equivalence of shared assessment identity to merged source rows. F4 has useful warning about defaults but proposed calendar-lookback-to-validity mapping is rejected.

## Main-Venue Codex Review

Adopt explicit evidence-node bindings and distinct derived requirement identities per binding; no stage-name guessing, no widening existing due-once identity, no mutation of already published node bytes. Preserve independent source origins and conditional applicability. Same-stage other-visit requirements must remain scoped to their own node, not block this node or disappear from the longitudinal view.

Do not require every evidence due node to be DECIDE_AT_NODE: evidence can legitimately be collected at an earlier explicit node for a later decision. The source-backed evidence binding must state where it is due; control role remains separate. Existing gate lines 3465-3477 only checks against global target stages, weaker than reviewer wording that implied membership in the control's own bindings.

Reject mapping CALENDAR_LOOKBACK into source_validity_window, even deterministically. A historical event lookback is not examination recency. Source type/contemporaneity/transcription/validity must come from explicit source-backed evidence semantics, not default guesses or a blanket failure for all timed obligations.

Do not reuse evidence_key alone when one evidence description expands to multiple node instances: derive identity from publication/control/evidence/node, retain original key as provenance. Keep recommendation and unknown applicability visible without unconditional blocking. Formal evaluator guard remains until full integration and deferred acceptance.

## Codex Independent Verification

Owner read full template projection, projection service and gate node closure; inspected typed temporal contracts and actual runner identity/usage. No staged tests, DB migration, model run or browser acceptance, per current user instruction. New contract implementation still pending.

## Final Decision

Proceed with explicit evidence binding design, then narrow modules and shared consumers. No user decision needed to preserve these existing clinical semantics; do not introduce a new clinical eligibility rule or declare T3 complete.

## Same-session Source-policy Follow-up

evidence_source_policy.md completed with terminal 0, 178.802s, 13 read-only tool calls; actual GLM-5.3 max verified, no fallback. Same session reduces context independence and is a follow-up, not a second model opinion. Output SHA256: 10e5b71f084f87e93f50fe951d059bb40156ad9fc35a7173e12151aba7ecfd1b. No tests/product calls reported. Owner read complete report and checked coverage/source-template consumers.

Adopt explicit source-policy unknown versus asserted values, source provenance, and sibling-node filtering in prior unresolved-input reconstruction. Keep current control IDs out of accepted requirement bindings until persistence is integrated. A missing result-validity constraint is not proof of unlimited validity; nor is it automatically an unknown requirement when the protocol explicitly has no separate limit. Temporal obligation evaluation remains separate.

Reject a single flat obligation_modality on each control-derived requirement: references must preserve mixed atoms/groups and exceptions, not flatten their strength. Reject waiting for subject applicability before creating protocol-wide immutable templates; subject applicability belongs in the episode evaluation. Do not permanently exclude recommendations from shared coverage: coverage and blocking consequences are separate. Unknown policy must stay explicit and cannot inherit legacy defaults. Newly constructed source-policy semantics require later final validation; this advisory report is not implementation or clinical acceptance.

## Same-session Control-evaluation Follow-up

evidence_control_evaluation.md ended 0, 239.730s, 20 tools, no fallback, empty stderr. Runtime GLM-5.3/max verified; SHA256 fbfe93a5429090058dedd0b7d3328440006dae1a65c534e5d7413acc2f5b60b9. Usage input158589/output5467/cacheRead157184; no API cost inferred. Same-context continuation, not an additional independent model. Owner read report and relevant contracts; no product call, migration or staged test.

Adopt the missing explicit control-atom proof identity and separate applicability/coverage, with full branch/exception IDs. Do not accept the report's claim that nullable policies cannot persist: the new shared fields accept None and exact mirror comparison preserves it. Unknown protocol policy is not absent patient evidence. Reject blanket exclusion of obligation atoms from semantic binding: prohibition, thresholds and behavioral requirements cannot all be satisfied by evidence presence. They need source-backed proof too. Unknown exception cannot prove either waiver or definitive failure; retain unresolved branches. Recommendations must not become exclusion findings. Existing evaluator's private time function still requires a ClinicalFact and AtomicExpression; reuse its arithmetic by an explicit pure-date interface rather than claiming such an interface already exists or fabricating predicates. The full-control guard remains until these consumers are implemented and final acceptance is performed.

## Layer-code Review and Integration

evidence_layer_code.md ended0, 261.488s, 14 tools; actual GLM-5.3/max verified, no fallback, empty stderr. Hash36933a98dfbaed42b6593de0bc81b4d628f1dc212eb9e6284196b37c24845954. Input181424/output3214/cacheRead180544. Same-context source review, not a new independent model opinion or runtime acceptance.

Owner adopted: reject unconsumed control-level time constraints; reject disjoint exception/replacement scopes; echo obligation kind/modality per atom, not just an aggregate truth; verify exception/obligation relations in both directions. Implicit unconditional route semantics are documented, not a new protocol interpretation. Unknown policy remains protected by the existing subject-projection guard and must gain explicit handling before its removal. Source review does not establish correct dates, prompt performance, atom correspondence, migration behavior or final clinical acceptance. The follow-up fixes were compiled, not tested, per user direction.

## Coverage-consumption Follow-up

evidence_coverage_consumption.md ended 0, 194.072s, stop, empty stderr; runtime requested/response GLM-5.3 max verified, no fallback. Same session, 9 reported tool calls (tool_result_count reported 0; do not equate this with independently verified tool execution). Input194782/output4489/cacheRead193856. Output hash4b207771b079161ba6c00d2c7cfd124b856a0578797f41df13afbc42663131d6. Owner read the report and complete affected source; compilation/import/diff checks only, no runtime or clinical acceptance.

Adopt source-target/reprojection consistency findings and the need to separate coverage from subject-level control activation; do not treat missing expectation rows as missing patient evidence. Reject applicability=TRUE as sufficient to activate every minimum evidence requirement: triggers, branch exceptions, replacement obligations and individual modality still matter. Also do not gate evidence needed to determine applicability on already-known applicability (circular prerequisite). Current minimum_evidence has no atom-role association, so no per-atom dependency can be inferred from fact_type or description in deterministic code.

Do not yet adopt the assertion that existing statuses suffice: OBSERVED_WEAK constrains risk/provenance reasons and cannot silently represent unknown protocol policy; nor does skipping a FALSE control preserve all existing useful observed facts by itself. A combined consumer must preserve evidence independently and expose unresolved activation, without misleading absent/weak classifications. The two current guards stay until a coherent consumer exists. The newly added control-v1 target is a source-preserving search input only; it does not activate a requirement or convert not_found into a clinical result.

## Dependency Implementation Follow-up

evidence_dependency_impl.md ended0, 259.119s, 17 reported tool calls, empty stderr; actual GLM-5.3/max verified, no fallback. Input213727/output2889/cacheRead212288. Output hash be1321ce9303a80caf2b325aad1a1754a925cbb836926a5f5916a9dcf223f96c. Same-session source review, no runtime or clinical acceptance. Owner adopted the source-chain findings and documented why legacy empty dependencies remain readable whereas a missing source policy cannot be defaulted.

Reject the proposed all-groups/all-mandatory absence formula: an inactive or recommended sibling must not suppress a separately active mandatory obligation sharing the same evidence. Preserve per-reference activation/modality, not a conjunction across all uses. Reject F2's suggestion that any resolved prerequisite clears the other unknown prerequisite uses. Unknown prerequisites and independently active obligations can coexist and must be reported separately without inventing applicability or silently suppressing a real requirement. A source reference association is not a verified patient truth, and this patch does not open either full-review guard.

## Proof-to-calculation Bridge Follow-up

evidence_proof_bridge.md ended0; actual request/response GLM-5.3 max verified, no fallback, empty stderr, 6 reported tool calls. Input221942/output4316/cacheRead221632. Output SHA256 8a9dea6203ef9439df585aa9ae64b8adc712944e3fe86cb1425557b0b690374f. Same-session source review, not a new independent opinion. Owner read the report and actual AtomicPredicate/_evaluate_atomic definitions. No product calls, DB work or staged tests.

Adopt reuse of the existing job lifecycle and a source-bound, versioned evaluation specification at protocol deconstruction, rather than reconstructing a predicate from prose when evaluating a patient. Existing explicit fact selection can bypass type buckets, but is not enough to evaluate arbitrary fact attributes: _evaluate_atomic still reads fact.value and its existing time semantics. Do not claim the evaluator can directly consume a selected record_time, assertion_basis or derived duration without explicit operand handling.

Reject blanket obligation-kind routing to coverage or automatic inversion for prohibition: a completed procedure has source-bound semantic conditions too, and the predicate may already express a negative proposition. Evidence presence and administrative action closure cannot establish compliance. Polarity/direction must be explicit in the published evaluation specification, not inferred again from kind. Also reject 'time mechanism zero changes': source validity and clinical interval evaluation differ, and an out-of-window value cannot always mean clinical FALSE. Copying a TimeConstraint alone does not settle temporal purpose. Canonical units or numbers need traceable source operands, not a naive verbatim string equality rule. These issues must be addressed before implementing the proposed adapter; candidate references remain accepted=false and both production guards stay.

## Evaluation Specification Source Review

evidence_evaluation_spec.md ended0; runtime GLM-5.3 max verified, no fallback. Input239224/output3584/cacheRead235072; 6 reported tools, tool_result_count0. Hash a72ddff73af48ba332c9c2f4ebead5e00844d2b9a3ddafcae5b8c7d2ddf14454. Same-session source-only continuation, not a new independent reviewer or runtime acceptance. Owner checked source after report and made the following decisions.

Adopt D4's one-way investigator-mode/atom-flag consistency and D5 optional operand_attribute for semantic tasks. Add explicit prompt warning against missing-record-as-absence, arbitrary ne sentinel values and inversion of exists. Do not prohibit all deterministic absence claims when a verified explicit boolean observation can genuinely support one.

Reject D1's blanket source_validity calculation ban: VERIFY_RESULT_VALIDITY already carries an explicitly sourced time constraint; its mathematical evaluation is legitimate. A consumer must reconcile it with the referenced evidence policy and cannot infer validity from a historical lookback. Reject D2's mandatory not_applicable when structured time is missing: unresolved is needed where interpretation is incomplete, and never licenses calculation or invents a window. Reject D3's kind-based ban on deterministic fulfillment: a deadline or explicit value condition can be calculated after correct evidence selection; coverage is not compliance. Do not forbid all occurrence/prospective fields (D6) merely because they are temporal; they express different source conditions. Unsupported calculation semantics must remain explicitly unresolved in the forthcoming consumer, not silently dropped. New wire/publication source checks establish structure only, not medically correct interpretation. Both full-review guards remain; no staged tests, clinical DB changes or product requests.

## Conditional Consumer Bridge Source Review

### Observation Policy Follow-up

evidence_observation_policy.md completed exit0; actual request/response GLM-5.3 max verified, no fallback. Input268046/output1560/cacheRead266176; seven reported tools. Hash 0aaca50862399bc701433a1e3ddedd0c640c8864bbdeb6ec50f8f73822adc23e. Same-session source review, not fresh independence. Source review supports explicit source-bound modes, old-field omission and three-valued conditional aggregation; these are not runtime or clinical acceptance.

Adopt B1's preservation need using per-observation truth/reason records rather than merging every reason into the aggregate: ANY can be true while a separate observation is unknown, and the aggregate must not falsely imply all evidence was resolved. Reject B2's repeated ban on legitimate source-validity arithmetic; purpose is explicitly retained and the experiment does not accept it without policy verification. Reject B3's repeated forced not_applicable where interpretation remains unresolved. Missing scope verification, latest/repeat replacement, semantic eligibility and formal proof remain explicit pending capabilities. Per-observation recording was added after this source review and has only compile/import checks.

evidence_consumer_bridge.md ended0, 319.366 seconds; actual request/response GLM-5.3 max verified, no fallback, empty stderr. Input255589/output2406/cacheRead255424; 11 reported tool calls, tool_result_count0. Output hash b9b62327ffe95945b094fce26f8e4e00f46d8541a359f35f5badf11d7c78c358. Same-session source review only, no fresh model opinion or clinical acceptance.

Adopt explicit temporal-purpose retention and a bounded isolated selection-to-composition entry. Reject universal ANY over observations: no source quantifier or observation selection policy has been supplied, and different dates/objects are not automatically a conflict. Reject treating every temporal FALSE as out-of-window: an explicit interval_condition can genuinely fail; event_membership cannot prove absence merely because one selected observation is outside its window. Reject repeated kind-based deterministic bans and mandatory not_applicable for unresolved source interpretation, for the previously documented reasons. Source-validity arithmetic remains legitimate, but its use as atom truth waits for source-policy correspondence.

Owner implemented control_calculation_experiment after this review: complete hash-bound atom selections; each selected pair validated; no type fallback; single deterministic observation can feed the existing layer composer conditionally. Missing/multiple observations, semantic modes, unverified source validity and unresolved dates remain explicit UNKNOWN. No first-observation selection, no model truth substitution, no production registration. All calculations remain accepted=false. The new consumer itself has not had independent source review or runtime validation; final concentrated tests must cover valid TRUE/FALSE cases as well as unresolved cases. Existing formal-review guards remain.
