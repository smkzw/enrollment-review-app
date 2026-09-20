Owner follow-up is source-only. I’ll re-read the listed contract, gate, evaluator, and report files and check the calendar-mask, sentence-scope, and date-only washout points against the actual diffs.The contract tightening is in place. Next I’ll read the control-gate mask, eligibility coverage check, wire schema, and date-bound comparison as they exist now.I confirmed day precision is a single calendar date with no clock. The remaining material issues are the date-only washout boundary and same-sentence generic subject binding. The rest of the owner’s listed fixes are present in source.

# Conference Output: r05-half-life-source-20260915 - evidence_single_object

**Fallback (explicit):** Same-session follow-up on `pi` / `cursor` / `cursor-grok-4.6` (high). Primary `grok-build` was never available. Direct file reads only; no pi-worker, tests, product, DB, or browser. Extra read beyond the listed packet: `app/domain/calendar_dates.py`, only to resolve `expression.py`’s `_date_bounds` for the date-only washout question. Advisory source review, not Codex acceptance and not clinical/PK validation.

## Output

### Evidence

Owner-claimed fixes are present in the listed files:

- **Same-sentence / single cue / approximation:** `HalfLifeEvidence.require_quoted_scope` (`half_life_evidence.py` L40–57) now requires exactly one `。！？；;\n` claim, exactly one `半衰期|half-life` cue, rejects `分别|各自|respectively`, rejects `applies_to_quote` that is the duration token or the cue word, and extends range/approximation (`或/或者/或为`, `左右/上下/以上/以下`, `平均|中位|median|mean|typically`). Null evidence is still popped (`rules.py` L146–150). No PK dictionary.
- **Control calendar mask:** `_check_time_constraints` (`protocol_control_gate.py` L2744–2750) blanks only `duration_quote` inside `source_excerpt` copies in the joined atom text; `_CALENDAR_DURATION_RE` / bound-prefix/suffix scan `calendar_text`; multiplier still uses original `source_text` (L2841–2846). Global evidence still `HALF_LIFE_SCOPE_UNRESOLVED` (L2671–2672).
- **Eligibility coverage:** `deconstruction_gate.py` L3342–3348 now also requires `source_excerpt` ⊆ some `component_draft.source_excerpts`, plus formal span ∩ `source_refs` ∩ `materials[span]` and `applies_to_quote` in `exact_source_clauses`.
- **Wire / matrix / action / version:** eligibility schema `value` is decimal string (`protocol_deconstructor.py` L542); object/null check L1749–1750; matrix prints cited duration only when evidence exists (`protocol_control_matrix.py` L2587–2591); PJ wording no longer swallows missing-half-life (`review_action_directives.py` L60–69); frozen evaluator remains `component-review/v17` (`frozen_review_calculation.py` L27) and still builds `EvaluationContext` without `half_life_days` (L216–222). Control operands still call `evaluate_time_constraint` without a duration table (`control_operand_calculation.py` L109–112).

**Date-only evaluation (washout boundary):** `date_bounds` for `DatePrecision.DAY` returns `(value, value)` — a point date, no clock. `evaluate_time_constraint` (`expression.py` L339–341, L374–401) then uses integer `.days`. Sourced duration stays `Decimal` (no ceil); it is always folded into an inclusive **lower** bound. For two day-precision dates, `distance_min == distance_max == D`. Inclusive check: `D < B` is false when `D == B`, `D < B <= D` is false, so the result is **TRUE**.

Example: last-dose date and first-dose/anchor date five calendar days apart, sourced bound `B = 5` days (or `5 × 24h`). Actual elapsed can be just over 4 days (dose at 23:00, anchor at 01:00) or almost 6 days. The evaluator still reports the window met.

Hour/minute sourced values make this sharper: `5 × 8h = Decimal('1.666…')` days vs `D = 2` → `2 < 1.67` is false → **TRUE**, while min elapsed can be ~1.0 day.

**Generic same-sentence subject:** uniqueness is of the duration token and of the half-life **cue**, not of the named product. `applies_to_quote` need only be a substring of that one sentence (`half_life_evidence.py` L23, L40–45). Coordinated subjects still compile, e.g. 「A药和B药的半衰期为14天」 with `applies_to_quote="A药"`, or 「与对照药X相比，本品半衰期为14天」 with `applies_to_quote="对照药X"`. Eligibility then only checks that this quote also appears in the washout predicate clauses (`deconstruction_gate.py` L3347), which does not restore the true PK subject.

**Narrow mask bug:** calendar blanking uses `str.replace(duration_quote)` (`protocol_control_gate.py` L2747–2749), not the unique regex span from the contract. In a comma-joined single claim (Chinese `，` is not a sentence splitter, L40), excerpt `本品11天洗脱，A药半衰期为1天` has one legal `1天` match; `replace("1天")` also rewrites `11天`.

Multiplier-only (`half_life_evidence is None`) still hydrates, gates skip evidence checks, evaluates to `half_life_missing` / `OBSERVATION_UNVERIFIED`, and is omitted from JSON. That path is intact.

---

### Inference

Prior blocking control-calendar collision is addressed for the intended inline-duration case, provided `duration_quote` does not suffix-overlap another calendar number in the same excerpt.

The remaining **material evaluation defect** is not quote syntax. With both timestamps date-only, calendar `D == B` (and `D == ceil(B)` for fractional hour/minute bounds) is treated as proof that washout elapsed. That is a clock-free **TRUE**, not an elapsed-hour proof. This is inherited from the existing date evaluator; sourced hour/minute values newly expose it because `in_days` is fractional while `.days` is integer. It is not pharmacological validation, and it is not fixed by v17 staying put.

The remaining **material source-adoption hole** is also not “quote existence vs science.” After the sentence/cue tighten, a compiled value can still be the duration of a coordinated or contrastive noun phrase while `applies_to_quote` is a shorter token in the same sentence. Substring scope ≠ the duration applies to this exposure. Proportionate close is syntactic refusal of coordinated/contrastive subjects, not a drug table.

Eligibility `applies_to_quote ∈ exact_source_clauses` is fail-closed and can also **over-reject** a legitimate footnote duration when the washout clause is only 「5个半衰期」 and does not repeat the product name. Multiplier-only remains representable if evidence is left null.

`str.replace` mask is a smaller implementation mismatch with the stated “exact quote span” policy.

---

### Recommendation

1. **Date-only washout (decide, then implement only for sourced evidence):**  
   When event and anchor are `DatePrecision.DAY` (no clock) and `half_life_evidence` is set, do **not** return TRUE for an inclusive lower bound unless even the shortest possible elapsed interval on those dates is ≥ `B`. Clock-free bounds: elapsed ∈ `(D−1, D+1)` days. TRUE only if `D − 1 >= B` i.e. `D >= B + 1`; FALSE only if `D + 1 <= B`; otherwise `UNKNOWN` / `ambiguous_time_window`. Do **not** invent times. Do **not** change historical calendar-only 「至少N天」 unless Codex explicitly expands the policy (that would need an evaluator bump for old runs). Sourced hour/minute should take this slack even if integer-day washouts stay on calendar-day convention. Integer sourced day/week can follow the same slack or keep calendar-day equality — that is D1 below. Version: bump `component-review/v17` only if any already-frozen sourced-evidence runs exist; null-evidence hashes stay stable.

2. **Coordinated/contrastive subject (proportionate, still not PK proof):**  
   In `require_quoted_scope`, require `applies_to_quote` to lie entirely in the prefix **before** the unique `半衰期|half-life` cue. If that prefix contains `和|与|及|以及|、|,|and|or|或者|相比|对照` and the prefix minus `applies_to_quote` still has non-punctuation, **refuse evidence** (keep multiplier, `half_life_evidence=null`). Do not NER drug names. Do not treat remaining substring match as applicability.

3. **Mask by span, not `str.replace`:** blank only the unique duration match span inside `source_excerpt` (the same `finditer` already used in the contract).

4. **Leave multiplier-only unknown.** No `half_life_days` fill, no drug table.

Non-blocking: wire-check `value` against the decimal-string pattern, not only `Mapping`; eligibility should not require the **product name** to be inside the washout predicate clause if the PK sentence is already in `component_draft.source_excerpts` (keep duration/applies-to inside that PK excerpt).

---

### Uncertainty

- No tests or model hydrate; Decimal vs JSON number on control wire (Pydantic schema, not the eligibility `_wire_time_constraint`) was not executed.
- Whether any frozen run already stores non-null `half_life_evidence` under `v17` is unread (artifact scan forbidden).
- Frequency of coordinated-subject PK sentences vs footnote-only duration is not counted.
- `calendar_dates.py` was an extra read for DAY point bounds; MONTH/YEAR partial-date paths were not re-audited for half-life.
- Quote/syntax success is not pharmacological applicability, population, assay, or accumulation.

---

### Objections, alternatives, decision points, bounded questions

**Objections**

1. Date-only inclusive equality currently **certifies** washout at the calendar boundary even though both dates lack clocks; sourced hours make a false TRUE more likely than integer calendar windows.
2. One-sentence/one-cue is still not subject identity; generic/coordinated text can compile another product’s duration.
3. `str.replace` is not the “exact quote” mask described.

**Decision points for Codex**

- **D1:** For sourced half-life, is the protocol measure **calendar dates** (keep TRUE at `D == B` for integer days) or **elapsed time** (UNKNOWN unless `D >= B+1`)? Hour/minute sourced units should not use calendar equality even if D1 keeps integer days.
- **D2:** Coordinated-subject refusal vs leave compiled and show quotes on the report for a person to reject. Recommendation: refuse compilation (null evidence, keep multiplier).
- **D3:** Evaluator bump vs “no frozen sourced evidence yet, keep v17”.

**Bounded questions**

- Q1: Any stored review already has non-null `half_life_evidence` under `component-review/v17`?
- Q2: Confirm D1 for hour/minute vs integer day independently.
- Q3: For eligibility, is `applies_to_quote ∈ exact_source_clauses` intentional even when the washout clause never names the product?

**Safe provisional path:** Keep multiplier-only as `half_life_missing`. Do not auto-TRUE sourced washout on date-only inputs at `D == B` (especially hour/minute). Do not compile evidence from coordinated/contrastive sentences. Do not add a drug table. Source compilation remains not clinical acceptance.
