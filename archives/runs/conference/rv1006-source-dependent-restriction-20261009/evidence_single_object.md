Trellis SessionStart context loaded. Proceeding with the bounded read-only review (no Trellis task — this is a delegated conference pass, not project work).

Bash is unavailable in this non-interactive session — I'll proceed with Read/Grep/Glob only and note the limitation. Now reading the four named definitions.

Key definitions read. Now the restricted-source service and the failure-assembly region, plus locating `partial_wire` and `include_owned_context` callers.

Now the critical region: the deconstructor insertion/review/failure assembly near lines 8950-10200 (this is where `partial_wire` is written), plus the definition-consumer validator definition.

# Conference Output: rv1006-source-dependent-restriction-20261009 - evidence_single_object

## Output

### 0. Scope, method, evidence trail, limitations

**Method:** read-only review of the frozen worktree at the assigned revision, reading only the declared definitions plus bounded adjacent consumers/tests. No source edits, no test execution, no network, no clinical artifact reads. `Bash` is denied in this non-interactive session and reading the worktree gitdir (outside workspace) was denied, so I could not verify HEAD `46237852…` by command; the evidence below is from the checked-out worktree contents I read. This is a stated limitation, not an assumption of identity.

**Evidence trail (all paths relative to the worktree root):**
- `app/agents/protocol_control_source_interpretation.py`: `is_non_action_definition` 1181-1197; `definition_consumer_candidate_atoms` 1220-1262; `build_source_definition_consumers_prompt` 1265-1381; `source_target_context_recheck_needed` 1601-1623; `build_source_target_review_prompt` 1626-1861; `validate_source_target_review` 1922-1938 (scope check); `validate_source_definition_consumers` 2326-2393; `require_frozen_official_predicate_identities` 2396-2435; `parse_product_source_definition_consumers` 2438-2456; `validate_restricted_definition_consumers` 2459-2490; `SourceStatement` 247-272 (incl. `scope_context_unit_id` 251); `SourceStatementCoverage` 852-865.
- `app/agents/protocol_control_deconstructor.py`: `build_result` 7125-7219; resume/partial wire 7119, 7221-7250; loop head/parse/hydrate 8017-8201; insertion success 9278-9308; alignment keep 9450-9484; context recheck call site 8981-9038; pending declaration failure assembly 9908-10028; success adoption 10029-10065; atom-repair baseline capture 9782-9789; failure-reason/attempt recording 9919-9987; `ProtocolControlAgentRunResult` fields 4345-4357; `declare_source_definition_consumers` 4365-4457; `hydrate_protocol_control_agent_output` 3998-4012.
- `app/services/protocol_control_restricted_source.py`: `_unit_statements_cover_source` 54-76; `_temporal_restriction_indexes` 125-195; `_restricted_capability_batch` 198-310; `_coexisting_statement_proofs` 313-414; `_whole_unit_restriction` 417-579; `_validate_restricted_definition_registration` 582-605; `_restricted_statement_batch_from_review` 608-821; `restricted_batch_from_review` 824-862.
- `app/domain/contracts/protocol_controls.py`: `RestrictedStatementIndependentExcerpt` 2137-2178; `RestrictedStatementScopeProof` 2181-2213; `RestrictedProtocolControlStatement` incl. `dependency_refs` 2237-2239, validation 2263-2277; catalog dependency validation 2385-2391.
- `app/services/protocol_control_execution.py`: restricted re-declaration and revalidation 3844-3899; publishable identity checks 3395-3398 and 3469-3471; checkpoint restore checks 1246-1272; private pending/diagnostic serialization 4410-4543.
- Tests consulted (names/lines only, no clinical content): `tests/v2/protocols/test_slice58c_control_deconstructor.py` 3341-3417 (pending declaration semantics), 13975-14039 (owned-context prompt identity), 14042-14069 (transport failure keeps siblings), 8989-8992 no; `tests/v2/services/test_control_source_definition_consumers.py` 467, 485, 528, 854, 893 (declaration/restricted consumer re-verification), `tests/v2/services/test_protocol_control_execution.py:6361` (execution context recheck).

**Limitations (explicit):**
- No test execution; no git HEAD verification (tool denial described above).
- Product author and this reviewer use the same DeepSeek model family through different contexts/transports: process/context separation, not model-independent medical evidence.
- I did not read run artifacts or any real protocol/subject content; the synthetic six-unit structure is treated only as a structural hypothesis. Where a conclusion depends on live clinical meaning or on the live wire's actual citations, I say so instead of inventing it.
- Recommendations are engineering proposals; they are not clinical approval, rule activation, or adoption authorization.

---

### 1. Does actual prompt construction omit bounded owned parent/context for cross-paragraph definition children?

**Finding (evidence):** Yes, by construction.

- `build_source_target_review_prompt` builds `read_only_sources` exclusively from `batch.context_units` (`protocol_control_source_interpretation.py:1690-1699`). `context_units` are out-of-batch read-only units (the test fixture literally labels one “只读上下文，不得处置”, `test_slice58c_control_deconstructor.py:206`); an owned parent paragraph is never there.
- With `include_owned_context=True`, `selected_units` is only the set of units of the statements currently under review (`selected_units = {interpretation.statements[index].structure_unit_id for index in indexes}`, 1702), and the packet includes each selected unit's full excerpt plus all statements of that same unit (1711-1719). So the packet can only supply (a) the reviewed unit itself and (b) same-unit sibling statements — exactly the two shapes the diagnostic observed.
- The only call site passing `include_owned_context=True` is `protocol_control_deconstructor.py:8989-8992`, and it is gated by `source_target_context_recheck_needed` (1601-1623), which requires `item.decision == "additional_requirement"`, the statement itself not `unresolved`, a frozen `target_id`, **more than one statement in the same unit** (`sum(... == unit.structure_unit_id ...) > 1`, 1618-1619), and literal unit-excerpt/target-excerpt equality. A single-statement child paragraph therefore never reaches even the same-unit recheck, and a cross-paragraph parent is never added by any path.
- `scope_context_source` (1646-1649) is only emitted when `SourceStatement.scope_context_unit_id` is set (247-251); it carries a table-label packet, not a generic prose parent link. No other cross-unit parent signal is persisted.
- `is_non_action_definition` (1181-1197) is only a *permission* to consider `definition_dependency` (emitted as `definition_dependency_allowed`, 1657); it is not a context carrier, and it explicitly withholds the shortcut from `unresolved` statements and requires definition-ish functions plus descriptive force.

**Smallest generic fix (proposal):** add an explicit, caller-computed owned-context closure to the prompt, derived from frozen literal citations rather than vocabulary:

1. At the call site (deconstructor 8989-8992), compute for the reviewed statement the set of other `batch.owned_units` that are cited by the same frozen candidate(s): for each frozen candidate in the current `wire` whose `source_structure_unit_ids` (or whose atom/evidence `source_span_ids`) intersect the reviewed statement's unit, collect that candidate's other `source_structure_unit_ids`, intersect with `batch.owned_unit_ids`, order by `source_order`, dedupe. Pass this as an explicit parameter, e.g. `owned_context_unit_ids: Sequence[str] = ()`.
2. In the prompt builder, render those units using the **existing** `owned_context` packet shape (unit id, `source_ref`, `source_span_ids`, full `excerpt`, all same-unit statements) — same identities, same ownership filter, no synthesis. Keep the existing disclaimers (“只提供关系上下文，不证明已有目标覆盖”, “不拼接兄弟，不改变兄弟处置”, 1704-1709) and the scope line `本次必须且只能返回这些 statement_index` (1840), so mutation stays target-only.
3. Keep the call cap (`context_reads >= 2`, 8982) counting the expanded read as one call. If no frozen candidate cites the parent, do **not** add it: keep the child in its existing unresolved/increment path (no parenthood inference from headings, adjacency, or disease vocabulary, and no reclassification of all definitions as obligations).
4. Do not broaden `is_non_action_definition` to “exceptions are definitions”; the defect is missing context, not classification.

**Cheap bounded variant (fallback):** include all owned units' excerpts in the recheck packet (batch-bounded, still identity-preserving, no new signal). Less precise and more prompt bloat; prefer the co-citation closure.

**Uncertainty:** the closure depends on the frozen wire actually citing parent+children (units or spans). I could not verify the live wire shape (no run-artifact reads). If the live wire lacks such citations, the safe provisional path is to leave the children unresolved and not synthesize a parent link.

---

### 2. Does actual insertion/failure assembly permit output and partial_wire to represent different versions?

**Answer: no on the publishable path; yes, deliberately, on the failure/diagnostic path — and that diagnostic divergence is currently unbound.**

**Publishable path is identity-enforced (evidence):**
- `output` is hydrated from `wire` and re-hydrated together with it (`output = hydrate_protocol_control_agent_output(wire, batch)`, deconstructor 8150, 8177; insertion updates them jointly: `wire, output, coverage = next_wire, next_output, next_coverage`, 9293).
- Success returns pass both from the same version (`final_output=output … partial_wire=wire`, 9633-9651; 10046-10065), and `build_result` re-derives coverage from `values["partial_wire"]` whenever `final_output` is present (7142-7145).
- The execution service re-checks the identity on adoption/resume: `hydrate_protocol_control_agent_output(result.partial_wire, batch) != result.final_output` raises at `protocol_control_execution.py:3395-3398` and `3469-3471`, with alignment revalidation following (3450-3456, 3484-3486). A publishable result cannot silently mix versions.

**Failure/diagnostic path permits divergence (exact control flow):**
1. An atom repair captures a pre-repair baseline: `pending_alignment_atom_baseline = (wire.model_copy(deep=True), deepcopy(coverage), candidate_alignment, target_review)` (deconstructor 9782-9784), then `partial_wire = revised; raw_text = revised.model_dump_json(); continue` (9786-9789). The next iteration re-parses and hydrates the **newer** wire (8017-8150).
2. A later `SourceTargetReviewValidationError(SOURCE_TARGET_REVIEW_UNRESOLVED)` lands in the handler at 9908-9913, which sets `partial_wire = wire` for that iteration, then runs the one bounded **pending** declaration against `output` (10000-10015, condition includes `output is not None`) and returns `partial_wire=partial_wire` plus `pending_source_definition_consumers` (10016-10028).
3. `build_result` then rolls the wire back: if `pending_alignment_atom_baseline is not None and values.get("final_output") is None`, it overwrites `partial_wire`, coverage, alignment and review with the saved baseline (7214-7219): “Keep the attempted reply in receipts, never expose an unvalidated edit as the draft.”
4. Net: the saved `partial_wire`/review are the older baseline while `pending_source_definition_consumers` was declared against the newer hydrated `output` — exactly the “one-candidate saved wire vs five-candidate declaration” symptom (the count difference arises whenever a candidate-adding step, e.g. insertion at 9278-9306, happened between baseline and declaration).

**Is that publishable? No (evidence):** the failure return keeps `status="需要核对"` with `final_output=None` (10016-10028); the declaration is explicitly diagnostic (“no adoption, no status change”, 9991-9997) and is serialized only into the private checkpoint (`_pending_definition_consumer_checkpoint`, execution 4513-4543). The restricted producers gate on the **adopted** field only (`result.source_definition_consumers`, restricted_source 428-433 and 648-651), and the restricted-path declaration is re-run against the actual restricted output (`_complete_restricted_deep_source`, execution 3844-3861), not reused from pending. `_validate_restricted_definition_registration` (582-605) only validates the adopted record.

**The defect:** nothing binds the pending declaration to the wire/output version it was declared against. Any future consumer (status/projection, replay, a “reuse saved declaration” optimization, debugging tooling) that resolves its `candidate_index`/`layer`/atom positions could resolve them against a different version than the one declared — the identity hazard this codebase otherwise refuses everywhere.

**Minimal identity-preserving fix (proposal):**
1. Record the anchor: add e.g. `pending_source_definition_consumer_anchor_sha256` to the run result, computed from the exact hydrated `output` (or its wire) passed to `declare_source_definition_consumers` at 10008-10014.
2. In `build_result`'s rollback branch (7214-7219), if the rollback changes the identity of `hydrate(partial_wire)`, drop the pending declaration and its attempts (or keep them with the anchor and an explicit non-adoptable marker). Distinguish this intentional diagnostic rollback from a publishable result explicitly.
3. At every reader, require `sha256(hydrate(partial_wire)) == anchor` before resolving declared atoms; never promote `pending_source_definition_consumers` into `source_definition_consumers`. Adoption must remain the re-declaration route (execution 3844-3861), whose pattern (raw text length + sha256 re-verification) is already the model to copy.

**Uncertainty / bounded question:** the `pending_alignment_atom_baseline` path is the only divergence mechanism I can prove from code. If the live failure did not involve a prior atom-repair attempt, I need the failure receipt's attempt trail (`recovery_method`, `pending_alignment_atom_baseline` presence) to locate the exact version-lag mechanism. The anchor-binding fix is version-agnostic and remains the safe provisional path.

---

### 3. Can R1 legally retain a fully sourced but non-executable parent and the independent administrative result when unresolved child sources are explicitly cited by the parent?

**R1 legality:** the product goal is consistent with R1 (“完整覆盖、例外驱动、先闭环再扩展”; affected items must not be falsely passed; preserve gap reason; keep independent results). The contract already has the carrier for “still depends on other restricted statements”: `RestrictedProtocolControlStatement.dependency_refs` (protocol_controls 2237-2239), validated as restricted-only, acyclic (2263-2277, 2385-2391) and consumed by status/projection (`protocol_control_status.py:172`, `review_history.py:293-346`).

**Code reality: not reachable today, and there are two independent blockers, not one.**
1. `_restricted_statement_batch_from_review` 704-710: for a unit with restricted indexes where independence is unproven, a single-statement unit is accepted only if the statement itself is `unresolved` or temporal. A fully sourced parent fails → the whole function returns `None`.
2. `_whole_unit_restriction` 462-466: it refuses unless at least one restricted unit is a `REQUIRED_PROCEDURE` or contains more than one statement. Four single-statement child paragraphs fail this gate *before* candidate handling runs. **A candidate-closure fix alone would still be gated out here** — this must be part of any decision.
3. Candidate removal: `_whole_unit_restriction` 513-522 requires `set(candidate.frozen_structure_unit_ids) <= restricted_units` for every removed candidate and forbids retained candidates sharing spans with restricted units. Candidate A (units 0-5) with independent unit 1 outside the closure is refused; `_restricted_capability_batch` has the analogous “one source unit per failed candidate” refusal (242-244), and `_coexisting_statement_proofs` refuses any candidate citing a restricted statement (368-375) — precisely the parent-cites-children shape.
4. Restricted units must also satisfy disposition + `_unit_statements_cover_source` (468-490, 488); that proof is available for a single-statement paragraph, but only once the closure-added unit is allowed in.

**Bounded-closure evaluation (as requested):**
- A closure `restricted_units = {unresolved/temporal units} ∪ {owned units the affected candidate/statement explicitly cites by frozen identity}` is computable from frozen data (unit ids, `source_span_ids`, candidate atom/evidence spans, `scope_context_unit_id` where present). With it, candidate A is wholly inside the closure except for genuinely independent units it also cites.
- Removing A is safe **only if** for every unit `u` outside the closure that A cites, every atom/evidence/relation of A whose spans intersect `u` is identity-carried by a retained candidate bound to `u` (same spans, verbatim excerpts, same kind/layer). Missing proofs that prevent a safe general implementation today:
  1. **No atom-level cross-candidate identity check exists.** Current protection is coarse unit/span-set intersection (513-522, 249-251, 753-756). Without atom-level identity, removing A can silently drop the only executable expression of a requirement in an unrestricted unit.
  2. **No producer computes or verifies the closure.** `dependency_refs` is never populated by either producer (`_whole_unit_restriction` 542-564; `_restricted_statement_batch_from_review` 770-790), and the parent→child link must be grounded in frozen citations, never prose similarity.
  3. **No “closure-added unit” path** with the same full-source coverage proof for the parent's own statements, and no validator that child restricted statements are the exact closure endpoints (no dangling/free-text `dependency_refs`).
  4. `RestrictedStatementScopeProof` is intra-unit only (2181-2213); it cannot express cross-unit independence and must not be stretched to try.
- **Verdict:** yes-with-proofs — a bounded closure over explicit candidate/source dependencies, atom-level identity for units left executable, verified full source coverage, and explicit `dependency_refs` for the parent is the right shape; refuse whenever any proof is absent. Do not delete the refusals, do not accept superset citations as independence, and do not widen the 462-466 gate for the no-closure case.

**Uncertainty:** whether the parent paragraph's citation of children is actually persisted as spans/units in the live frozen wire (vs only wording) is not verifiable from code alone. If it is wording-only, the closure cannot be built and the correct R1 outcome is a hard refusal (whole-unit restricted or no restricted output), not an inferred dependency.

---

### 4. Minimal positive, meaning-preserving, counterfactual, and recovery/consumer tests

Grounding: keep the existing identity-focused pattern (`test_slice58c_control_deconstructor.py:13991-14069` asserts frozen bytes unchanged and exact prompt context). Suggested additions, all synthetic:

**Q1 — prompt context (positive/negative/counterfactual):**
1. Positive: six-unit fixture (parent unit 0 conditional action with numeric limit; independent admin unit 1; children 2-5), candidate A cites units 0-5. Assert `build_source_target_review_prompt(..., include_owned_context=True, owned_context_unit_ids=…)` for a child includes unit 0's exact `excerpt`/spans/statements, that all ids come from `batch.owned_units`, that `本次必须且只能返回这些 statement_index` lists only the child, and that `batch`/`interpretation`/`review` bytes are unchanged.
2. Counterfactual A: remove candidate A from the wire → no parent block (no vocabulary inference).
3. Counterfactual B: a foreign `statement_index` answer is rejected and the original review/sibling kept (mirror `response_kind="foreign"`, 14042-14069), with a transport failure variant.
4. Meaning-preservation: with parent context present, a child that is only meaningful with the parent must not be auto-converted into an independent requirement/insertion attempt — assert no insert path is entered and the unresolved aspects survive verbatim.

**Q2 — version binding (positive/counterfactual/recovery):**
5. Extend `test_runner_reaffirmed_function_requires_one_valid_target_review` (3341-3417): with a prior atom-repair baseline, assert the returned `pending_source_definition_consumers` carries an anchor equal to the hashed hydrated output it was declared against; counterfactual without rollback → anchor equals `hydrate(partial_wire)`; assert in all failure shapes that `source_definition_consumers is None` (never promoted).
6. Recovery: rehydrate/serialize round-trip (deconstructor 7119/7219, execution 1246-1272, 4448-4470) — assert the anchor is preserved or the declaration dropped consistently; assert `_pending_definition_consumer_checkpoint` (4513-4543) keeps raw answers private and unchanged.

**Q3 — restricted closure (positive/counterfactual/recovery):**
7. Positive (only after the proposed proof exists): parent 0 fully sourced, children 2-5 unresolved, candidate A cites 0-5, candidate B cites unit 1 only → restricted output retains B and unit 1's disposition; restricted statements for 0 and 2-5; parent's `dependency_refs` point exactly at the children's restricted ids (acyclic, restricted-only).
8. Counterfactual A: add one unit-1-only obligation atom to A not present in B → refusal (`restricted_batch_from_review` returns `None`).
9. Counterfactual B: alter one span/excerpt in B → refusal. Counterfactual C: no citation evidence for parent→children → refusal.
10. Consumer/recovery: `_validate_restricted_definition_registration` (582-605) rejects a declaration whose raw text/hash differ; execution re-declaration (3844-3895) requires `revalidated == restricted_batch` byte-identical; mirror `test_restricted_definition_consumer_is_reverified_saved_and_consumed_without_calculation` (`test_control_source_definition_consumers.py:854`), and keep 467/485/528/893 green.

---

### 5. Most important objections, proposed solutions, decision points

- **O1 (highest impact):** even a correct candidate-closure fix is defeated by `_whole_unit_restriction` 462-466 (“procedure unit or multi-statement restricted unit”). Decide explicitly whether dependency-restricted single-paragraph units qualify; otherwise the closure never runs. Safe default: extend the gate with the closure proof rather than removing it.
- **O2:** the live run treated exception explanations as independent requirements. Prompt context (Q1) is necessary but may be insufficient if the insertion compiler (`can_compile_*`/`source_statement_is_standalone_action` paths) still accepts a context-dependent child as standalone. I did not audit the stage compiler in this pass; the repro should assert no insertion attempt for such children when the parent context is supplied.
- **O3:** never promote `pending_source_definition_consumers`; today’s code does not, but it lacks a version anchor. Bind it before any reuse optimization lands.
- **O4:** `dependency_refs` exists and is already trusted by status/projection but has no producer; adding one must be citation-verified and cycle-checked, never free text.
- **O5:** do not “fix” this by broadening `is_non_action_definition`, calling all definitions patient obligations, or inferring parenthood from headings/adjacency/disease vocabulary.
- **Decision points for Codex:** (a) accept the co-citation closure as the Q1 fix, or the all-owned-units bounded variant? (b) Is dependency-only parent restriction inside the RV1006V1 window, or a separate bounded task per “仅直接阻断或错误采用保护修复准入”? (c) For Q3, accept the atom-level identity proof as the only route to keeping unit 1 executable, with refusal otherwise?
- **Bounded questions (same-session answerable):** (1) Did the live failure include a prior atom-repair attempt (`pending_alignment_atom_baseline` non-null) — i.e., is the proven version-lag path the actual one? If not, provide the failure receipt’s attempt trail. (2) Does the live frozen wire cite the parent paragraph for the children by unit/span identity, not only by wording? (3) Confirm that no consumer currently reads `pending_source_definition_consumers` except the private diagnostic checkpoint.
- **Safe provisional path if input is missing:** apply the Q2 anchor binding regardless (cheap, version-agnostic), do not implement the Q3 closure without the citation evidence, and leave the children unresolved rather than synthesizing parenthood.

---

### 6. Recommendation summary

1. Q1: confirmed omission; implement the explicit frozen co-citation owned-context closure (bounded, identity-preserving, read-only, target-scope unchanged), or the batch-bounded all-owned-context fallback; never infer parenthood.
2. Q2: publishable results are identity-safe; the failure/diagnostic assembly intentionally rolls back `partial_wire` while the pending declaration remains unbound. Bind the declaration to its declaration-time wire/output identity and drop or mark it on rollback; never promote it.
3. Q3: R1-legitimate but not currently reachable; implement the cited closure + atom-level identity proof + produced/validated `dependency_refs`, and keep every existing refusal and the 462-466 gate for unproven cases.
4. Q4: the minimal test set above, in the existing two test files, covering positive, negative, counterfactual and recovery/consumer paths.

All recommendations are engineering proposals; no clinical meaning was invented, and Codex retains final integration and acceptance decisions.
