I'll run the assigned read-only conference review: first load the two initial context/plan files, then audit against the allowlisted evidence only.Next I’ll audit the allowlisted scoring/reread scripts, harness, and frozen pilot assessments for concrete counterexamples.I’ve found a likely high-impact gap in pair compatibility checks; verifying route effort defaults and whether field-name equality is enforced.# Conference Participant Output: r3-reread-evidence-audit-20260906 - general_single_object

## Boundary Check

- Worked only in the phase5 worktree; used the conference allowlist only.
- No file writes, no clinical/product model calls, no credential/`.env` reads, no outside-worktree raw clinical sources, no other conference outputs.
- Did not claim clinical/image QC sign-off; source-image conclusions in assessment files are treated as Codex-reported QC, not re-verified here.
- Runtime identity: conference role `pi` / provider selector `cursor` / model selector `default`. Underlying model identity was **not** independently verified from an adapter receipt in this session; do not equate selector with verified product model identity.
- Deterministic local checks only (`PYTHONDONTWRITEBYTECODE=1`, `.venv/bin/python`); no live tests against clinical endpoints.

## Independent Work Product

### Audit posture (pre-draft challenge)

Assumptions under challenge:
1. “Two isolated conflict-reread pilots + exact-key scorer + product `read_page` end-state handling” ⇒ enough to greenlight auto-acceptance wiring.
2. Observation pairing score ≈ value agreement / clinical fact recall.
3. Isolated experiment scripts already embody the product conflict-reread contract in `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §2026-09-06.

All three fail under the allowlisted evidence.

### Finding 1 — Auto-acceptance is **not** justified (policy conclusion, evidence-backed)

**Evidence**
- `artifacts/.../conflict-reread-blind-02/assessment.md`: same image `dbc3a062…`; two high/high blind rounds; P-LCC remains A=`27↑` vs B=`27↓`; Codex QC says printed mark is `27↓`; stop after two business rounds; `product_acceptance` remains false; “当前不足以…批准自动采信”.
- `artifacts/.../conflict-reread-second-layout-02/assessment.md` + `main-B-length-retry.json`: different layout `e12d0a42…`; MiniMax first-round row misbind (LYMPH%/EO% take neighbor-row values); second-round MiniMax `finish_reason=length` then budget retry still `length` with `raw=""` / `output_tokens=0` while `completion_tokens=8000`; no third business round; no single-lane release; `product_acceptance=false`.
- Design proposal (`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md:198-211`): isolated verification, **not** connected; auto-acceptance policy and new performance thresholds explicitly undecided.

**Inference**
Pilots demonstrate (a) persistent glyph-level disagreement after two rounds, and (b) incomplete/failed second-lane completion that must terminate as unresolved—not as silent agreement or majority vote.

**Recommendation**
Do **not** authorize automatic acceptance ingress. Keep end states partitioned at least as: `source_conflict_persists`, `reread_incomplete` (incl. length exhaustion), `identity/provenance_unresolved`, `researcher_judgment_missing`.

### Finding 2 — Highest-impact engineering defect: `check_pairs` under-reports field mismatch

**Proved bug (compatibility diagnostic), not clinical ruling**

`scripts/evaluate_observation_alignment.py:68-102` validates duplicates, unknown IDs, value/unit via `normalize_scalar`, arrow marks, and context/time/polarity. It never compares `field_name` (or equivalent projected field id).

Local counterexample (same page/lanes, same value/context, different `field_name` `P-LCC` vs `WBC`):

- `rejections == []`
- `accepted is False` (hard-coded)
- therefore a “clean” rejection list can hide a cross-field pairing

**Why it matters**
`accepted=False` prevents false product acceptance today, but empty `rejections` can be misread as “compatible pending QC,” corrupting conflict taxonomy and any future gate that keys off rejection reasons.

**Minimal remediation**
Add an explicit rejection such as `field_name_mismatch` (and, if context carries specimen/object text, a separate object mismatch). Keep `accepted=False` / `source_qc_required=True`. Add a unit test beside `tests/v2/services/test_observation_alignment_experiment.py`.

### Finding 3 — Exact-key scorer is correct for its narrow contract; unsuitable as clinical auto-trust

**Evidence**
- `scripts/score_exact_fact_keys.py`: requires explicit projection (`project_id/subject_id/image_sha256/field_id/context_id/polarity/raw_value/unit`); arrows via `source_arrow_marks`; `clinical_acceptance` always `False`; duplicate gold/IDs fail closed.
- Tests (`tests/v2/evidence/test_exact_fact_scoring.py`) cover cross-field/specimen/date-role/unit/polarity/arrow misses, zero retention, duplicate prediction dilution, empty-denominator `None`.
- Benchmark audit (`.trellis/.../BENCHMARK_SCORING_AUDIT_20260906.md`) shows historical loose `num_norm`/`fact_hit` overclaim; exact-key primitive is the intended corrective, not a full recall substitute.

**Local counterexamples**
- `27↑` vs `27↓`: `normalize_scalar` both `('27', None)`, but scorer recall `0.0` because arrow marks differ — correct separation of numeric norm vs source annotation.
- Chinese prose “向上箭头” yields `source_arrow_marks == ''` — glyphs only; prose explanations do not encode arrows.

**Limits that block formal acceptance use**
1. No bridge from `evaluate_conflict_reread.Reread.Observation` (`field` / `value_with_unit` / `excerpt`) → `ScoredFact` projection.
2. No alias/date-role/identity inference by design; cannot score free-text reread fidelity alone.
3. Empty/ambiguous gold still requires adjudication outside this primitive.
4. Does not measure excerpt faithfulness (blind-02 notes A’s non-verbatim explanatory excerpt).

**Recommendation**
Keep as isolated projected-key metric only. Any reread evaluation needs an explicit projection+adjudication step before calling `score()`.

### Finding 4 — Observation correspondence ≠ value agreement (must stay split)

**Evidence**
- `score_pairs` (`evaluate_observation_alignment.py:33-49`): exact ID-pair set metrics; `product_acceptance=False`; no value compare.
- `check_pairs`: value/arrow/context diagnostics on proposed pairs; still never accepts.

**Inference**
A high pair-ID recall can coexist with systematic value disagreement (or silent field mismatch per Finding 2). Union/pairing metrics must not be sold as dual-source value agreement or auto-trust.

### Finding 5 — Product normal-finish vs isolated reread end-state gap

**Evidence**
- Product `read_page` (`app/llm/page_review_harness.py:520-545`): one `length` → double `max_tokens` retry; second `length` → `failure_kind="length"`; non-`stop` → refuse acceptance (`failure_kind="schema"`). Covered by harness tests (`test_length_finish_retries_once...`, `test_nonterminal_or_unknown_finish_cannot_accept...`).
- Formal routes: main-A `reasoning_effort="low"`, main-B `"high"` (`require_page_reader_routes` ~187-202). Conflict experiment forces **both** lanes to `"high"` (`evaluate_conflict_reread.py:65`), matching the targeted-reread proposal, not formal first-pass.
- Isolated `evaluate_conflict_reread.run`: on non-`stop`, raises and keeps receipt; **no** built-in length retry. Second-layout length retry was an external one-shot with prior receipt hash — correctly classified as non-business round in assessment.
- Design (`:208`): business cap = two rounds; transport/length retries counted separately and not unbounded; one lane’s success cannot clear the other’s failure.

**Inference**
Product page-read finish handling is stricter/more complete than the isolated reread script. That is acceptable for a probe, but it is **not** evidence that durable conflict-reread coverage, predecessor linkage, failure taxonomy, and user-handoff are implemented.

**Minimal next implementation (engineering only)**
1. Fix `check_pairs` field-mismatch rejection + tests.
2. Add a thin shared “completion policy” helper used by isolated reread: one length double-budget retry; persist attempt_kind; never count as business round 3.
3. Define durable unresolved statuses mapping to user queue; do not implement auto-resolve.
4. Optional eval-only: explicit projection adapter from reread JSON → `ScoredFact` **after** human/Codex projection rules—not model self-projection.

### Finding 6 — Second-layout identity caveat blocks subject-level claims

Assessment records filename/dir identity mismatch (`06001` vs `06002`) and treats the trial as in-image read only. Any subject-linked acceptance, coverage chain, or gold binding remains blocked until provenance is resolved (Codex-owned).

## Evidence And Assumptions

| Kind | Item |
|---|---|
| Evidence | Blind-02 persistent arrow conflict after 2 high/high rounds; second-layout MiniMax misrow + double length failure; both assessments refuse auto-trust |
| Evidence | Exact scorer separates value vs arrows; always `clinical_acceptance=False` |
| Evidence | `check_pairs` omits `field_name` compare; local counterexample `rejections=[]` |
| Evidence | Product `read_page` length-once + non-stop refuse; formal main-A remains low |
| Evidence | R3 2026-09-06 proposal: isolated, max 2 business rounds, no majority/auto-trust |
| Assumption | Assessment image QC statements are Codex-reported, not re-verified here |
| Assumption | No unseen later artifact overturns these two pilots within allowlist |
| Uncertainty | Vendor usage paradox (`completion_tokens=8000` vs `output_tokens=0`) root cause unknown; record, don’t invent |
| Uncertainty | Adapter `cursor/default` ≠ verified runtime model id |

## Risks, Gaps, And Verification Needs

1. **Auto-acceptance creep**: wiring “both high agreed once” without durable conflict taxonomy would violate pilots + design.
2. **Metric conflation**: pairing recall / historical union recall / exact-key recall / dual-source acceptance must remain separate columns.
3. **Excerpt fidelity unmeasured**: free-text explanation can pass schema while violating “只抄录可见…摘录”.
4. **Script/product parity**: isolated reread lacks product length/429/fallback policy; product lacks conflict-reread task graph.
5. **Projection gap**: cannot auto-score reread outputs with `score_exact_fact_keys` without an audited projection layer.
6. **Verification needs (Codex-owned, not done here)**: reproduce field-mismatch unit test; confirm no product path sets acceptance from isolated scripts; keep `claims_complete=false`; no threshold ratification from n=2.

### Objections to the implicit “ready enough” path

- Objection: pilots “mostly worked” ⇒ soft-launch auto-trust.  
  Counter: the failing modes are exactly the release-critical ones (glyph conflict; row bind; truncated empty body).
- Objection: `accepted=False` everywhere means pairing diagnostics are safe.  
  Counter: empty rejection reasons are still an observability/contract bug and will poison future gates.
- Objection: exact-key scorer “replaces” old benchmark claims.  
  Counter: it only scores already-projected keys; audit explicitly forbids using it as full clinical recall.

## Recommended Next Step

**Codex should treat auto-acceptance as blocked**, and authorize only this minimal engineering follow-up (no clinical sign-off, no threshold approval, no product model calls in-conference):

1. Patch `check_pairs` to reject `field_name` mismatch (proved bug) + test.  
2. Document/freeze end-state enum distinguishing persistent source conflict vs incomplete reread vs unresolved identity vs missing researcher judgment.  
3. Keep isolated reread as diagnostic; if shared completion policy is added, mirror `read_page`’s single length retry without creating a third business round.  
4. Do **not** connect auto-acceptance until: projection bridge exists, multi-layout failure modes have adjudicated gold, and user-approved policy/thresholds exist.

### Decision points for Codex

1. Confirm auto-acceptance ingress remains **forbidden** on current evidence.  
2. Approve/deny the `field_name_mismatch` minimal code fix in a later edit round (this pass was read-only).  
3. Decide whether length-retry parity belongs in `evaluate_conflict_reread` now or only when a durable product reread task is designed.

### Bounded questions for Codex

1. Should `check_pairs` compare raw `field_name` strings only, or normalized field ids via an already-approved alias table? (Affects false conflict vs silent cross-field pairs.)  
2. For second-layout `06001`/`06002` identity mismatch: is subject binding deferred indefinitely for scoring, or is there an allowlisted provenance artifact to use next?  
3. Is the intended first product end-state for MiniMax double-`length` empty body `reread_incomplete` (my provisional path), or a more specific `provider_empty_completion`?

**Safe provisional path if unanswered:** keep `product_acceptance=false` / `clinical_acceptance=false` / `claims_complete=false`; classify both pilots as non-acceptance diagnostics; fix field-mismatch reporting before any workflow wiring; do not auto-resolve conflicts from single-lane success or length-retry artifacts.
