I’ll re-read only the changed contract, mask, and evaluator paths and check the open-interval and token-boundary claims against the current source.The first batch used the wrong reader name. Retrying with the workspace Read tool on the same changed files.The three claimed edits are in source. Next I’ll check reason mapping, DateValue clock limits, and whether the open-interval PK check can hide an independent calendar FALSE.# Conference Output: r05-half-life-source-20260915 - evidence_single_object

**Fallback (explicit):** Same-session follow-up, `pi` / `cursor` / `cursor-grok-4.6`. Direct reads only. Advisory source review, not Codex or clinical acceptance.

## Output

### Evidence — claimed control flow is in source

**Subject prefix (`half_life_evidence.py` L47–53).** After the one-sentence / one-cue checks, `applies_to_quote` (NFKC, stripped) must be a prefix of the text before the unique `半衰期|half-life` cue. Coordinators/contrast markers (`和|与|及|以及|、|,|，|或|相比|对照|and|or|compared|versus`) in the **remainder** reject compilation. Syntax only.

**Mask (`half_life_evidence.py` L67–76; `protocol_control_gate.py` L2746–2750).** `mask_duration` finds one raw `duration_quote.strip()` with `(?<![\d.．])…(?![\d.A-Za-z．])` and blanks that span. Calendar/prefix/suffix scans use `source_text.replace(excerpt, mask)`. Multiplier still uses original `source_text`. `11天` is not eaten by quote `1天`.

**Elapsed slack (`expression.py` L383–391).** Sourced evidence: FALSE if `distance_max+1 <= duration`; UNKNOWN `half_life_time_precision_insufficient` if `distance_min-1 < duration`; otherwise **does not** fold PK into `lower_bound`. Legacy `half_life_days` still `ceil` into `lower_bound`. Calendar-only unchanged.

**Version / reasons / clocks.** Evaluator `component-review/v18`; recalc refuses other versions (`frozen_review_calculation.py` L27, L164–168). Reason mapped to `DATE_OR_ANCHOR_MISSING` (`assessment.py` L239), frontend note (`reviewConditionNotes.ts` L48), action says do not invent times (`review_action_directives.py` L70–74). `DateValue.value` is `date | None` (`common.py` L23–26); `source_text` is not consumed as a clock.

Open interval on date-only DAY points: elapsed ∈ `(D−1, D+1)`. `D+1 <= B` ⇒ max `< B` ⇒ FALSE; `D−1 >= B` ⇒ min `> B` ⇒ not UNKNOWN. Inclusive lower bound is consistent with that open interval. Partial-date `distance_min/max` plus the same ±1 is the intended extra clock slack.

---

### Remaining substantive issue (must-fix for combined windows)

PK UNKNOWN **returns immediately** and never runs calendar bounds (`expression.py` L388–389 then skip L392+). That does not match “calendar continues independently.”

For `longer_of_calendar_and_half_life`, required elapsed is `max(calendar, PK)`. A calendar miss is already a miss:

- Calendar 90 days, PK 70 days, `D=70`: PK hits `69 < 70` → UNKNOWN. Calendar `70 < 90` would be FALSE. Current result: UNKNOWN.
- Calendar-only and PK-only paths are unaffected. Combined success path (PK not UNKNOWN) still applies calendar afterward.

**Fix:** order as (1) PK FALSE → FALSE; (2) evaluate calendar as now; (3) calendar FALSE → FALSE; (4) PK UNKNOWN → UNKNOWN. Do not invent clocks. Bump stays `v18` if this ships before any v18 freeze; otherwise `v19`.

---

### Open-interval / mask check (not must-fix)

- FALSE uses `<=` on `distance_max+1`; UNKNOWN uses `<` on `distance_min-1`. That is the open interval, not an off-by-one against inclusive PK duration.
- Same-day / hour-minute washouts stay UNKNOWN. `DateValue` still cannot close that with uploaded clock text.
- Mask digit boundaries are correct for `1天` vs `11天` / `21天` / `1.5天` vs `5天`.
- Validator uniqueness is NFKC; `mask_duration` is raw. Mismatch fail-closes with `ValueError` in the control gate rather than `HALF_LIFE_SOURCE_UNVERIFIED` (operational, map the error if you want a typed reject).

---

### Advisory (syntax ≠ applicability)

- Prefix-start plus remainder markers stop `A药和B药的半衰期为14天` and `与对照药X相比，本品半衰期为…` with a short `applies_to_quote`. It does not prove the quote is the PK subject.
- Remaining compile cases: English `vs`/`vs.` (not `versus`); population/assay modifiers after a short prefix (`本品在肝损害患者的半衰期为14天` + `applies_to=本品`); over-reject of `停用A药，其半衰期为…` because `A药` is not at the start of the prefix.
- Proportionate: add `\bvs\.?\b` if English protocols matter; do not add a drug table. Keep multiplier-only as null evidence.

---

### Decision points / questions

- **D1:** Combined-window UNKNOWN vs calendar FALSE — implement the reorder above?
- **D2:** Map `mask_duration` uniqueness failure to `HALF_LIFE_SOURCE_UNVERIFIED` vs let `ValueError` fail closed.
- **Q1:** Any freeze already stored as `component-review/v18`? If yes, combined-window reorder needs `v19`.

**Provisional path:** Do not TRUE date-only sourced washout at `D == B`. Do not treat `source_text` clocks as computable. Do not fill `half_life_days`. Combined windows: do not report UNKNOWN when calendar already FALSEs. Compilation is not clinical acceptance.
