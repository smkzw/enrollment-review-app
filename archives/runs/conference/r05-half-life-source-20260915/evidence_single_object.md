Delegated conference pass for `evidence_single_object`. I’ll start from the assigned context and plan, then audit the half-life source contract and related code without writing files or running the product.Context is loaded. Next I’ll read the half-life contract, deconstruction gates, and frozen-review consumers against the assigned source list.Grep didn’t hit `half_life` even though the contract file exists, so I’ll search those source files directly and read `TimeConstraint` plus the deconstructor/gate consumers.The contract is in place. I’ll now trace source validation, evaluation, freeze/hash, and report display through the listed consumers.Highest-impact issue is already clear: control-path calendar-bound checks can reject the exact inline duration this increment is meant to accept. I’ll lock that against the remaining hash/display path, then return the full conference report.# Conference Output: r05-half-life-source-20260915 - evidence_single_object

**Fallback (explicit):** The assigned primary `grok/grok-build/grok-4.6:high` was unavailable before a resumable session existed. This pass was executed as the declared `pi` fallback `cursor` / `cursor-grok-4.6` (high). Capability limits: no product/model/DB/browser/tests (forbidden by the packet); one `pi-worker` dispatch failed at CLI startup, so all evidence is from direct file reads and `rg`. Pydantic float→`Decimal` coercion was not executed. This is advisory source review, not Codex acceptance and not clinical/regulatory validation.

## Output

### Evidence

**Contract (new exact-duration object)**  
`HalfLifeEvidence` (`app/domain/contracts/half_life_evidence.py`) stores `value: Decimal > 0`, unit ∈ {minute, hour, day, week}, plus `source_span_id`, `source_excerpt`, `applies_to_quote`, `duration_quote`. After-validate rules:

- `applies_to_quote` and `duration_quote` must be substrings of `source_excerpt`.
- `duration_quote` must **full-match** `\s*(\d+(?:\.\d+)?)\s*(分钟|小时|天|日|周|minutes?|mins?|hours?|hrs?|days?|weeks?|min|h|d|wk)\s*` after NFKC, and that number/unit must equal `value`/`unit`.
- Excerpt must contain `半衰期` or `half[ -]?life`.
- The normalized `duration_quote` must occur **exactly once** in the excerpt (`(?<![\d.])…(?![\d.A-Za-z])`).
- Prefix immediately before that occurrence may not end in `<>≤≥~～—–-` / `至|到|约|大于|小于|至少|最多|about|approximately|between|to`; suffix may not start with `~～—–-|至|到|to|and` + digit.
- `in_days(multiplier)` converts with 1440 min / 24 h / 7 d per week, returning `Decimal`.

`TimeConstraint` (`app/domain/contracts/rules.py` L68–151) adds `half_life_evidence: HalfLifeEvidence | None`. Evidence without `half_life_multiplier` is rejected. Calendar + multiplier still requires explicit `combined_window_selection=longer_of_calendar_and_half_life`. Serializer **pops** `half_life_evidence` when `None` (`preserve_historical_duration`). `ON` forbids multiplier/windows; evidence is not named in that tuple, but evidence⇒multiplier so `ON` still fails closed.

**Deconstruction / source ownership**  
Eligibility prompt (`protocol_deconstructor.py` L362–366) and control prompt (`protocol_control_deconstructor.py` L1364–1367) both: keep multiplier if duration is absent; fill evidence only from this atom’s formal source; no memory/drug-name/other-population/range-endpoint substitution.

Eligibility wire schema includes nested evidence (`protocol_deconstructor.py` L538–549, JSON `value` type `number`). `_wire_time_constraint` (L1748–1799) **passes the raw dict through** with no shape/quote check; Pydantic runs later on `TimeConstraint`.

Eligibility gate `HALF_LIFE_SOURCE_UNVERIFIED` (`deconstruction_gate.py` L3315–3370) requires, when evidence is present:

- `source_span_id ∈ component_draft.source_refs`
- `source_span_id ∈ allowed ∩ formal_ids`
- `source_excerpt` is a substring of `materials[source_span_id]`
- `applies_to_quote` appears in some `predicate.exact_source_clauses`

It does **not** require `source_excerpt`/`duration_quote` to appear in `component_draft.source_excerpts`, nor sentence-level binding of applies-to ↔ duration.

Control gate `_check_atom_sources` (`protocol_control_gate.py` L1883–1891) is tighter: some parallel `(span_id, excerpt)` pair must satisfy `evidence.source_span_id == span_id` and both `source_excerpt` and `applies_to_quote` ⊆ that atom excerpt. Global control-level evidence is rejected (`HALF_LIFE_SCOPE_UNRESOLVED`, L2671–2672). Multiplier must appear as `N个半衰期` / `N half-lives` (`_HALF_LIFE_DURATION_RE` L231–234, check L2834–1845).

Control calendar extraction (`_CALENDAR_DURATION_RE` L164–167: `\d+` + 天/日/周/月/年/days?/…) does **not** exclude half-life duration quotes. Then (L2741–2767): if any calendar duration is found and `lower_bound`/`upper_bound`/`_*_days` are empty → `TIME_CALENDAR_BOUND_MISSING`. Prefix `至少N天` etc. must be a subset of structured calendar bounds (`TIME_BOUND_COMPARATOR_MISMATCH`, L2828–1832).

No hardcoded PK/drug table was found. `half_life_days: dict[str, float]` remains on v1 `ReviewContextSnapshot` and `EvaluationContext` only.

**Frozen evaluation**  
`evaluate_time_constraint` (`expression.py` L374–386): if multiplier set:

1. sourced evidence → `Decimal` duration via `in_days(Decimal(str(multiplier)))`, **no ceil**;
2. else if `half_life_days` argument is set → `Decimal(str(half_life_days)) * multiplier`, then **`ceil`**;
3. else `UNKNOWN` / `half_life_missing`.

Half-life duration is always folded into **`lower_bound = max(lower_bound or 0, half_life_bound)`** (minimum elapsed time). Distances are integer `.days` from date-only values.

Frozen V2 path (`frozen_review_calculation.py` L216–222) builds `EvaluationContext` **without** `half_life_days` (defaults `{}`). Control operands (`control_operand_calculation.py` L109–112) call `evaluate_time_constraint` **without** `half_life_days`. Predicate proposition calc still *can* pass `context.half_life_days.get(subject.attribute)` (`predicate_proposition_calculation.py` L73), but the frozen builder does not populate that dict. V2 snapshot (`review_context_v2.py`) has **no** `half_life_days` field. Recalc refuses if `rule_set_sha256` or `evaluator_version` (`component-review/v17`) mismatch.

`half_life_missing` maps to `GapType.OBSERVATION_UNVERIFIED` (`assessment.py` L238). Action text asks for sourced duration, not a drug name (`review_action_directives.py` L60–64).

**Report**  
`review_history.py` `_half_life_basis` (L413–418) emits applies-to, duration quote, multiplier, and `source_excerpt` onto condition `calculation_basis` and control `calculation_basis`. Frontend decoder requires `calculation_basis` (`reviewHistoryHttp.ts` L497, L512); `FrozenReviewReport.tsx` L119/L163 and `frozenReviewExport.ts` L40/L57 print/export those strings. `reviewConditionNotes.ts` L47 maps `half_life_missing` to a missing-data note. Control matrix label (`protocol_control_matrix.py` L2587–2588) still prints only `半衰期倍数=…`, not evidence.

---

### Inference

The increment’s intended fail-closed policy is visible and mostly consistent: multiplier-only protocols stay legal; missing duration → `half_life_missing` / unverified, not a invented PK value; null evidence is omitted from JSON so historical `rule_set_sha256` should stay stable; frozen V2 does not inject a drug table.

The **highest-impact source defect** is on the control gate, not the Decimal evaluator. A legitimate inline duration such as「停用至少 5 个半衰期。XXX 的消除半衰期为 14 天。」is exactly what `half_life_evidence` is for: multiplier=5, evidence=14 day, **no calendar window**. `_CALENDAR_DURATION_RE` still captures `14天`. With empty structured calendar bounds, `_check_time_constraints` raises `TIME_CALENDAR_BOUND_MISSING`. If the sentence is「半衰期至少为 14 天」, `TIME_BOUND_COMPARATOR_MISMATCH` also fires. That **rejects the protocol this increment was added to accept**, or forces the model to stuff 14 days into `lower_bound`, mixing calendar washout with PK duration.

Second, quote-existence is not claim-identity. Uniqueness is only of the **duration token** inside a caller-chosen excerpt, and `半衰期` may appear anywhere in that excerpt. Range suffix does not include Chinese `或`; `左右` / `平均` / `中位` / `median` / `mean` are not blocked. A multi-drug paragraph can bind drug A’s `10天` to drug B’s applies-to quote if both strings occur in the same excerpt. Eligibility is weaker than control: duration may live in `materials[span]` without being in the component excerpts a reviewer sees. Substring presence is **not** pharmacological applicability (packet scope); it is also not even a same-clause source proof.

Third, evaluation assumptions: sourced fractional days vs integer calendar distances are **equivalent to ceil for inclusive lower bounds**; exclusive bounds correctly avoid double-ceil. Half-life is always a **lower** elapsed-time bound. English hyphen `14-day` cannot be a `duration_quote` (fail-closed, not false adoption). JSON schema `number` for `value` is a precision footgun relative to `Decimal`. `_wire_time_constraint` deferring evidence validation is fail-closed on hydrate, but makes it easy for a model to null the field to pass wire checks.

Report/export wiring for sourced evidence is present on the frozen history path. Matrix text is an adjacent omission, not the print report.

---

### Recommendation (minimal revisions)

1. **Control calendar vs PK duration (must-fix before using this on control atoms)**  
   In `_check_time_constraints`, when `constraint.half_life_evidence` is set, exclude the span of `duration_quote` (and ideally the same sentence) from `_CALENDAR_DURATION_RE` / `_TIME_BOUND_PREFIX_RE` / `_TIME_BOUND_SUFFIX_RE` matches. Do **not** treat that number as a missing `lower_bound`/`upper_bound`. Keep `TIME_HALF_LIFE_UNSUPPORTED` on the **multiplier** (`N个半衰期`) only. Eligibility has no equivalent trap; do not “fix” it by copying the control calendar rule.

2. **Tighten `HalfLifeEvidence.require_quoted_scope` (same-claim, not same-excerpt)**  
   Minimal closed rules, still quote-only (no drug table):
   - Require `applies_to_quote` and `duration_quote` inside the **same sentence** (reuse control’s `_STRONG_CLAUSE_BOUNDARY_RE` or equivalent `。！？；;`).
   - Reject a second `半衰期|half-life` in that sentence unless it is the same token.
   - Extend range/approximation: suffix `或|或者|或为|左右|上下`; prefix `平均|中位|median|mean|typically`.
   - Optionally allow a hyphen in `duration_quote` (`14-day`) as an exact-quote form; not required for safety.

3. **Align eligibility `HALF_LIFE_SOURCE_UNVERIFIED` with control ownership**  
   Require `evidence.source_excerpt` ⊆ some `component_draft.source_excerpts` (or the predicate clause set already used for applies-to). Keep formal-span ∩ `source_refs`. Do not require duration inside the washout predicate clause (footnote/table row on the same component is legitimate).

4. **Leave multiplier-only unknown**  
   Do not populate frozen `half_life_days`. Do not add a drug table. Action/report copy already asks for sourced duration; keep it.

5. **Hash / version**  
   Keep popping null `half_life_evidence`. Adding non-null evidence **should** change `rule_set_sha256` and block recalc of old runs. No evaluator bump is required for historical multiplier-only records (same UNKNOWN/ceil path). If Codex later changes exclusive-bound semantics for sourced values on already-published evidence, bump `component-review/v17` then.

6. **Non-blocking polish**  
   Wire-validate `half_life_evidence` as object|null in `_wire_time_constraint`. Prefer JSON string/decimal for `value`. Include evidence in `_time_constraint_text` if matrix remains a reviewer surface. Name `half_life_evidence` in the `ON` forbidden tuple for symmetry.

---

### Uncertainty

- Did not run tests or instantiate models; `TIME_CALENDAR_BOUND_MISSING` is a static control-flow conclusion from L2741–2767 + L164–167, not a live gate trace.
- Pydantic v2 float→`Decimal` equality vs `duration_quote` string is unread at runtime.
- Whether current dirty tree already bumped `component-review/v17` / control experiment `v10` for this increment was not git-blamed.
- No protocol corpus was read; frequency of「半衰期为 N 天」without a separate calendar washout is inferred from the increment’s stated purpose, not counted.
- `protocol_control_matrix` is adjacent documentation, not the frozen report; impact on reviewers is unknown.
- Half-life-as-upper-bound / “whichever longer” on a lookback **upper** window is assumed unused; code always maxes into `lower_bound`.

This is not clinical, PK, or regulatory acceptance. Quote match ≠ the duration applies to this drug, this population, or this assay.

---

### Objections, alternatives, decision points, bounded questions for Codex

**Objections**

1. Control `TIME_CALENDAR_BOUND_MISSING` currently fights the new contract’s happy path. Shipping evidence without that exclusion will either block sourced durations or push models to duplicate PK days into calendar bounds.
2. `applies_to_quote in source_excerpt` + unique `duration_quote` is too weak to stop cross-drug / range-endpoint adoption inside a generous excerpt. That is the main remaining “adopt a different drug/population/duration” hole; range `或` is a concrete regex miss.
3. Eligibility source check is not the same ownership proof as control (`materials[span]` vs atom excerpt). Reviewers can be shown a washout clause while calculation uses another paragraph on the same span.

**Proposed solutions**  
Prefer (1)+(2)+(3) above as one small patch set. Do not solve (1) by allowing global `half_life_days` again.

**Decision points (Codex)**

- D1: Is control-path inline duration in-scope for this increment, or eligibility-only until a later control patch? If in-scope, (1) is blocking.
- D2: Same-sentence vs same-excerpt for applies-to↔duration: same-sentence is the minimal closed rule; same-clause-window is stricter.
- D3: Hyphenated English `14-day`: fail-closed (current) vs add an exact-quote alternative.

**Bounded questions**

- Q1: Should `_check_time_constraints` treat `half_life_evidence.duration_quote` as **non-calendar** even when the unit is 天/周? (Needed to implement D1.)
- Q2: For eligibility, is `source_excerpt ⊆ component_draft.source_excerpts` acceptable, or must duration also appear in `exact_source_clauses`?
- Q3: Any already-frozen rule_set JSON in this worktree that would change hash if the serializer failed to pop null evidence? (I did not scan stored artifacts.)

**Safe provisional path if unanswered:** Treat control inline-duration as **not publishable** until D1 is fixed; eligibility sourced values may be compiled but not clinically accepted; multiplier-only remains `half_life_missing` + evidence request; do not fill `half_life_days`.
