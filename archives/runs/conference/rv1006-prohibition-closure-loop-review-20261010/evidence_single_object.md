Trellis SessionStart context loaded.

Beginning the read-only review. First, locating the specified functions in the authorized read set.

## Output

### 0. Scope, method, and what was not done

Read-only review of frozen HEAD `7067b423e4a97eae195451cb824ed0406651c61d` inside the bound worktree. Focused reads:

- `app/protocols/protocol_control_gate.py` (gate:170-220; 479-497; 2596-2656; 3020-3080; 3080-3191; 4806-4923; 4932-4949)
- `app/protocols/protocol_control_repair_errors.py` (1-240)
- `app/agents/protocol_control_deconstructor.py` (7060-7190; 10260-10560; 11214-11237)
- `tests/v2/protocols/test_slice58c_control_deconstructor.py` (8490-8610; 10530-10660); greps across `tests/v2/protocols/test_slice58c_protocol_control_gate.py`

Not done, and not claimed: no tests executed, no runtime observed (the 25-call job is owner-reported metadata only), no clinical raw material, no network, no full-file scans. All conclusions below are static source reading plus inference, labeled as such. The enclosing function name of the TIME_ANCHOR_MISSING producer (gate ~3020-3191) was not resolved (my def-list grep started at gate:3508); I cite it by line range.

Independence disclosure, up front: I am running DeepSeek-V4.1-Flash on the CodeBuddy route. The product under review also uses a DeepSeek route. Therefore my *model-behavior* inferences (why the agent rewrote prose, how it reacts to prompts) are correlated with the product family and are weak evidence; the *structural* claims (producer metadata, identity composition, stop conditions, budget paths) are model-independent and are what I rely on. I did not use the network to verify anything about the model route.

---

### 1. Highest-impact finding (F1): the no-progress "located defect" stop is structurally unreachable for both reported codes

**Evidence (source, direct):**

- `_located_publication_failure_identities` (deconstructor.py:7080-7096) emits an identity only when *all* of these hold: `not error.repair_scope_unknown`; `item["entity_id"] in owners` where `owners` maps **bare candidate IDs** to index (7087-7095); non-empty `item["structure_unit_ids"]`; truthy `item["json_path"]`; `message` is a str.
- ENROLLMENT_PROHIBITION_UNCOVERED producer (gate:4912-4921) sets `entity_id=unit.structure_unit_id`, `structure_unit_ids=[unit.structure_unit_id]`, `obligation_source_span_ids=unit.source_span_ids`, and **no** `json_path`. It is one issue per unit (`break` at gate:4922).
- TIME_ANCHOR_MISSING producer (gate:3164-3169) calls `_fail(..., entity_id=f"{entity_id}/{atom_id}")` with **no** `structure_unit_ids`, **no** `json_path`, **no** spans. `_fail` defaults confirm this shape (gate:479-497); the error class also defaults `json_path=None` (gate:86-110).
- The stop rule (deconstructor.py:10313-10320) counts a located key `(identity, "located-publication-defect", "")` and stops at `>= 2`; the fallback `invalid_fingerprint` includes `raw_output_sha256` (10305-10311), so it requires a byte-identical answer twice.

**Conclusion (high confidence):** For UNCOVERED the identity fails on `entity_id in owners` and `json_path`; for TIME_ANCHOR_MISSING it fails on all three of owner-match, units, `json_path`. `located_fingerprints` is therefore empty, and the only surviving stop condition is a byte-identical rewrite — which contradicts the owner-reported fact that whole-answer hashes vary. The designed early stop ("the same source-located publication defect despite a rewritten answer, observed for the second time", docstring 7111-7116) cannot fire for exactly the two codes that repeated. This is the earliest causal error I can locate; it is not a gate-judgment error.

**Contradiction that proves the intent exists elsewhere:** the repair-scope resolver in repair_errors.py resolves the composite entity correctly — `candidate_for_entity` splits on `"/"` and falls back to `control_to_candidate` (repair_errors.py:117-125) — and the repo pins that behavior: `test_atom_level_gate_error_keeps_owning_candidate_repair_scope` feeds `entity_id = candidate_id + "/atom-1"` with empty units and asserts the owning candidate and unit scope are granted (tests:10551-10569). So two resolvers for the same kind of finding disagree: one understands `owner/atom`, the other requires an exact owner ID plus metadata the real producers never emit.

**Another contradiction (F4, same root):** the only test of the located-recurrence mechanism constructs findings by hand with `json_path="/trigger_expression/groups"` and `structure_unit_ids=("su-01",)` (tests:8524-8532) and asserts the clock does not reset when candidate IDs/prose change (8504-8546). The real gate producers for these two codes emit no `json_path` at all. The mechanism is verified only against fabricated metadata, which is why the mismatch survives the suite.

**Minimal coherent fix (proposal, no new authority):**

1. Producer metadata (the load-bearing fix): TIME_ANCHOR_MISSING must carry the owning entity's `structure_unit_ids` and a stable `json_path` for the atom (the enclosing validator at gate ~3020-3191 is already inside a per-entity validation that knows the containing entity; assume as an unverified precondition that the owning candidate's frozen unit ids are reachable there — if not, see Q1). Do not add spans if the atom's source spans are not known, since the identity does not require them.
2. Owner resolution parity: resolve `entity_id` in `_located_publication_failure_identities` with the same prefix rule and `control_to_candidate` map used by `publication_repair_error`, instead of exact-match against candidate IDs. Keep the other guards (`json_path`, units, `repair_scope_unknown`) unchanged so no repair authority is invented for genuinely unknown locations.
3. Unit-level identity for UNCOVERED (see C below): the finding's real locator is the structure unit plus its source spans. Define its identity on `(code, structure_unit_ids, obligation_source_span_ids)` and do not include model-generated prose. Do not add a `json_path` to a unit-level finding just to satisfy the helper.
4. Do not touch the `>= 2` threshold, the counter scope, or the budget constants. The stop remains cumulative, per-location, and failure-preserving: findings stay in `validation_findings`/`error_class_codes` (repair_errors.py:209, 219-226), the run ends `需要核对` with `final_output is None` (pattern proven at tests:8497-8546), and a *different* defect at a *different* location still gets its first occurrence.

**Alternative explanation I could not exclude:** if the failing job never reached the closure/insertion branches (see F3) and instead looped through generic repair paths where `repair_scope_unknown` is true, `_located_publication_failure_identities` returns `()` by its first guard (7085-7086) regardless of metadata. In that world the identity fix is necessary but not sufficient, and the generic-path repetition needs its own bounded stop. Distinguishing requires the run receipt: which branch set `allow_source_insert` vs `allow_source_closure_rewrite`, and how many attempts show `repair_scope_unknown=True`. This is my top bounded question to Codex (Q1).

---

### 2. F2 (B, first half): source-insert priority does suppress non-source findings from the repair message text

**Evidence:** in `publication_repair_error`, `messages` renders `repair_scope_issues` **only when** `allow_source_insert` is true; in every other branch it renders all `issues` (repair_errors.py:112-115). In the source-insert branch, `repair_scope_issues` is only the `SOURCE_INSERT_GATE_CODES` (88-93), so a co-occurring TIME_ANCHOR_MISSING is absent from `messages` while still present in `error_class_codes` (209) and `validation_findings` (219-226). In the closure-rewrite branch `allow_source_insert` is forced False (84), so messages include everything — no textual concealment there.

**Inference:** whether this is real concealment depends on what the repair prompt renders. `missing_source_statements` / `source_statement_inventory` are built for the source paths (deconstructor.py:11214-11237), but I did not read the prompt template or the wire→prompt formatting, so I cannot say the model never sees the time finding. If the prompt is messages-only, the model is asked to repair a rejection whose stated scope is a prohibition-coverage problem while an independent atom-level time defect is not shown, and the atom-level finding can only reappear via the next full publication pass. That is a plausible contributor to "six repeats".

**Minimal correction (one line of behavior, no scope change):** always populate `messages` from `issues` (the scope that matters for the model's *authority* is already carried structurally by `candidate_ids`/`structure_unit_ids`/`allow_*` flags), or add the omitted codes explicitly. This does not widen repair authority; it only stops information loss.

---

### 3. F3 (B, second half): closure rewrite breadth is guarded, but over-inclusive at unit granularity and span-blind

**Evidence for the guard (credit where due):** the deconstructor expands a closure only over candidates sharing flagged units (10495-10519) and then voids the permission if the closure union escapes the authorized units (`source_closure_authority_escape`, 10520-10529; `repair_scope_unknown` fold-in, 10546-10559). So "broad rewrite" cannot silently escape the flagged unit set. My initial suspicion of unbounded rewriting is not supported.

**Residual defects, still worth fixing minimally:**

- `_partial_prohibition_candidates` (repair_errors.py:39-54) selects any candidate whose frozen units are `⊆` the issue scope **and that contains any `prohibit_*` atom**. It does not require the candidate's prohibition to cite the uncovered clause. Every candidate entirely inside the flagged unit therefore becomes closure-mutable, including unchanged siblings — precisely the "unnecessary broad rewriting" the objective asks about. The gate file already has the source-bound helpers that would narrow this (`locate_source_quote_offsets`, gate:4932-4949; `candidate_cites_unit_quote`, gate:5000), and the ambiguity rule at 4946-4948 shows the codebase's own standard: an ambiguous sub-span proves nothing. Narrowing the predicate to "a `prohibit_*` atom whose excerpt maps into the uncovered clause's unit range" is minimal and source-bound.
- `obligation_source_span_ids` is deliberately emptied for closure rewrites and repartitions (repair_errors.py:204-208), so the returned error drops the span-level identity for exactly the repairs with the largest blast radius. Keeping the spans would let the runner's span checks (`unknown_obligation_spans`, 10530-10532) constrain the round.
- Consumer correction, if F2 is accepted: keep the union of findings in messages while `repair_scope_issues` continues to govern authority.

**Do not** delete or merge a duplicate atom as a "cleanup": the duplicate may be the only atom quoting the clause (that is what makes it a coverage candidate at all). The objective's instruction is correct and I endorse it.

**Not verified (disclosure):** how `mutable_candidate_source_keys`/`mutable_candidate_indexes` are enforced when the repaired wire is rebuilt; I read their construction (10561-10621) but not the enforcement site. I therefore do not claim the model *can* rewrite a sibling; only that the authority granted includes it.

---

### 4. F5 (A): coverage does demand a whole compound sentence in exactly the cases where a legitimate atomic decomposition exists — and I recommend keeping that for now

**Decisive evidence:**

- Coverage credit is exact-match only, with four routes: restricted-statements exact `(unit, quote)` pair (gate:4814-4817, 4869-4870); `normalized_quote ∈ quoted_clauses`, where `quoted_clauses` are normalized **full `[。；;\n]`-delimited sentences** of a linked candidate's atom excerpts and only when `normalized == statement` or the whole quote equals the sentence (4844-4865); the split shortcut; official/procedure quote coverage with span intersection or the narrow 摘要/排除标准 table-row case (4876-4911).
- The split shortcut (gate:170-220) currently admits only *period-only prefixes*; the comment at 211-215 states it explicitly: "This shortcut supports period-only prefixes, not conditions assigned to only one half. Unsupported language needs the ordinary semantic path." It also requires the two halves to share the identical suffix after the prohibition word, identical spans, and `statement == evaluation.proposition` — i.e. it forbids the natural decomposition into two independent atoms with their own statements. Its second consumer, `_modality_source_for_atom` (2607-2631), also depends on it, so any widening changes modality-cue selection too.
- Therefore: for the synthetic pattern (parent trigger + embedded conditional prohibition + independent permission), and for any compound where a condition attaches to one half, an atomic decomposition that quotes only its own verbatim sub-span and holds the parent dependency in a sibling atom is **rejected**, even though every atom is source-located. An atomic decomposition that keeps the whole clause verbatim in at least one atom's `source_excerpts` passes regardless of atom count or statement shape. Coverage is over-excerpts, not statements — the "legitimate atomic representation" is accepted *if and only if* it retains the full sentence as a quote.

**Reasonable alternative explanation (and why I give it weight):** the docstring states the gate's purpose — stop explicit stage-scoped prohibitions "vanishing as no-op rows" (4810) — and the comment at 4841-4843 assigns semantic coverage to the source review, not to regex. The failure asymmetry in this product (a false UNCOVERED costs one review round; false coverage can silently drop a prohibition from the published catalog, which is exactly the class of error the project treats as hard-reject) plus the shared shortcut with modality selection mean widening is the dangerous direction.

**Recommendation:** keep the rejection as the current behavior. If a future narrowing is wanted, the only shape I can defend is a *conditional partition proof*, not substring matching: atom A's excerpt maps uniquely into the clause via `locate_source_quote_offsets` (ambiguity → reject, 4946-4948); the remainder of the clause is covered by another atom/continuation bound to the same unit with matching `source_span_ids`; A carries its own prohibition word and its own time/condition qualifiers. Dangerous negatives that such a proof must still reject: (a) a conditional half whose parent trigger is covered by no sibling; (b) a sub-span occurring more than once in the unit; (c) a quote that covers the clause while the covering atom's statement describes a different action — coverage must never become semantic approval; that stays with the other validators.

**On the seven-day sibling variant:** the current code is correct to refuse sibling substitution. At gate:3148 the fallback is `atom.time_constraint or global_time_constraint` — an explicit global, never a sibling. The one-constraint-per-atom requirement is enforced per atom (3148-3169). I found no path that lets a sourced sibling window discharge a time-bearing atom, and none should be added. This is a genuine strength to preserve with a regression (see D2).

---

### 5. F6/F7: two smaller but concrete gaps

- **F6, control-owned findings cannot be located at all.** `_located_publication_failure_identities` receives only `candidate_ids` (deconstructor.py:7082, 10313-10314). `publication_repair_error` has `control_to_candidate` for exactly this reason (repair_errors.py:117-125). If TIME_ANCHOR_MISSING fires on a control entity, even prefix resolution cannot produce an identity. The fix in F1.2 must consult the same mapping.
- **F7, first-defective-atom-only reporting.** The producer raises on the first atom lacking an anchor (gate:3134-3169 inside the loop over `atom_groups`; `_fail` raises), so one validation pass can surface only one missing anchor per expression. A candidate with several time-defective atoms requires one round per atom. This is correct for atomicity but multiplies calls; it should be documented in the budget contract and is directly relevant to the call-count discrepancy below.

**Call-count discrepancy (unresolved, flagged honestly):** the runner docstring bounds calls as roughly initial + ≤1 transport retry + ≤2 schema repairs + one insertion + one future-prohibition + one calendar correction (7099-7126), which is far below 25. But the suite shows per-candidate repair calls via `continue_candidate` (tests:10585-10605) and additional review/coverage calls exist in the loop. I could not enumerate all call sites within the read budget, so I state the discrepancy rather than explain it: either additional call classes exist beyond the docstring, or the docstring's budget contract is incomplete. For C ("stop recurring calls while preserving cumulative budgets") the practical consequence is identical: the identity stop is the only per-defect brake, and it is inert for these codes.

---

### 6. Direct answers

**A.** Yes, in the precise sense above: for conditional compound sentences and for decompositions that quote only sub-spans, coverage requires the full `[。；;\n]`-delimited clause verbatim in some linked atom's excerpts, or an official/procedure/restricted exemption. Evidence: gate:4844-4865, 170-220 (comment 211-215), 4814-4817, 4876-4911. Alternative explanation: intentional conservatism with asymmetric failure cost, sharing logic with modality selection (2627-2629). Verdict: rejection should stay; a source-bound partition proof is the only widening I can defend, and it must carry the dangerous negatives listed in F5.

**B.** Yes for message-text concealment in the source-insert branch (112-115 omits non-source findings while still carrying them structurally); and yes for over-inclusive closure membership at unit granularity (39-54 selects any prohibit_* candidate inside the flagged unit). No for unbounded rewriting: the escape guard (10520-10529, 10546-10559) bounds the closure to flagged units. Minimal corrections: always render all findings in `messages`; narrow `_partial_prohibition_candidates` to clause-citing prohibit atoms; retain `obligation_source_span_ids` on closure rewrites instead of emptying them (204-208).

**C.** Typed identity (proposal): `{code, entity_kind: candidate|structure_unit, candidate_index|null, json_path|null, structure_unit_ids (non-empty required), source_span_ids, message_sha256}` with these rules: (1) emit only when location is provable — unknown location emits nothing and grants no authority (keep 7085-7086 byte-for-byte); (2) candidate-owned: resolve `owner` or `owner/atom` prefix and map controls through `control_to_candidate`; require `json_path` (for atoms, the stable schema path of the atom, not the atom's generated id); (3) unit-owned (UNCOVERED): candidate-agnostic key on `(code, unit_ids, spans)`, one issue per unit already (gate:4922), no model prose in the key; (4) do not hash model-authored prose: move the appended 原句 out of the TIME_ANCHOR_MISSING message (gate:3167) into a structured field, since paraphrasing the statement currently resets the clock; (5) keep the existing `>= 2` counter and per-key independence so distinct same-code issues (pinned by tests:8549-8560) keep distinct clocks; (6) known limitation to document: identity uses candidate *index*, so a candidate reorder resets the clock — the 8506 test covers ID/prose change, not reorder. This stops recurrence without suppressing failures (findings remain in the receipt) and without spending the remaining budget.

**D.** Regression family (small, connected; all proposals, none run):
1. Gate positive: shared-action sentence split by periods with a `not_due_at_review_node` continuation → covered (pins gate:170-220).
2. Meaning-preserving variant: reorder the periods / swap the separator set ("和"/"及"/"、" variants in 216-220) → still covered; same clause with one half carrying a condition → must stay UNCOVERED (dangerous counterfactual for F5).
3. Failure/recovery loop (real gate codes): build the finding through the actual producers — for TIME_ANCHOR_MISSING use a candidate fixture and run the real gate so the finding's metadata is producer-shaped (unit ids present, json_path present after the fix), not a `SimpleNamespace` (contrast tests:10551-10569) — then feed a rewritten answer with changed candidate IDs and prose that repeats the defect; assert exactly two publication attempts, "停止自动修订", `final_output is None`, and the finding still in `error_class_codes`. Mirror for UNCOVERED at unit level; add a distinct second unit that must still receive its first attempt.
4. Real downstream consumer: a batch-level test through `validate_protocol_control_batch_candidates` / `check_protocol_control_batch_candidates` (gate:5252, 5315) asserting the exact metadata contract that `_located_publication_failure_identities` consumes. This is the test whose absence allowed F1/F4.
5. Time-sibling negative: atom with no own constraint while a sibling has a sourced window → TIME_ANCHOR_MISSING stays (pins gate:3148).

**Proved vs. proposed:** proved from source — producer metadata shapes, identity preconditions, counter behavior, message-scope behavior, guard behavior, first-atom-only reporting. Proposed — all fixes and all tests. Uncertain — the failing branch mix, the prompt rendering, wire enforcement of mutable keys, and the call-count accounting.

---

### 7. Objections, decision points, and bounded questions for Codex

1. **(Q1, blocking my confidence in F1's sufficiency)** From the failing receipt: which branch fired first — `allow_source_insert` or `allow_source_closure_rewrite` — and how many attempts carried `repair_scope_unknown=True`? Why it matters: the identity fix is necessary for both branches, but if the generic/unknown path dominated, a second bounded stop is needed and the "one insertion only" rule should already have braked the insert branch. Safe provisional path: implement the identity/ownership fix only; change nothing else until the branch mix is known.
2. **(Q2)** Is `linked_control_candidate_ids` (consumed at gate:4846) authored by the agent or computed during hydration? I could not locate the producer within budget (`protocol_control_hydration.py` does not exist at that path — my path guess was wrong; the function is imported as `hydrate_protocol_control_agent_output` in tests). If it is computed, the coverage gate may be structurally unfixable by any candidate rewrite, which would make a hard stop plus an explicit review hand-off the only correct behavior — and would change the priority of this whole review from "repair the loop" to "stop and report". This is the one input that could overturn my "minimal fix" recommendation.
3. **(Q3)** Does the repair prompt render `messages` only, or also `error_class_codes`/`validation_findings`? If messages-only, F2's one-line fix is required before any further budget is spent.
4. **(Q4)** Confirm that the identity helper may consult `control_to_candidate`; the helper currently has no such parameter and adding one touches the runner call site (10313-10314) and the test at 8550-8558. I propose extending the parameter list with a defaulted mapping to keep existing callers green.

**My strongest objection to the framing of the review:** the objective invites "challenge the gate", but the source shows the gate's producers and the repair loop's identity consumer were built to different contracts and were *tested against different fixtures*. The gate's judgment (conservative, exact-source coverage; no sibling substitution; no guessed anchors) is defensible and I would not change it without clinical evidence I do not have. The defect is in the loop's observability of its own failures. Fixing the loop first is also the smaller, reversible change and preserves the option to revisit coverage with real source material later.

**Remaining uncertainty after budget:** (a) the enforcement site of `mutable_candidate_source_keys` — I did not read it, so I do not claim the model can or cannot rewrite a sibling candidate; (b) the full call-site inventory behind the 25-call count; (c) the original job's branch mix and prompt rendering (Q1/Q3); (d) the enclosing producer function name at gate ~3020-3191. I stopped at the 12-section budget rather than broadening; if Codex wants (a), (b), or (d) resolved, that is the exact remaining work, and I do not need same-session follow-up unless Q1/Q2 answers change the priority.
