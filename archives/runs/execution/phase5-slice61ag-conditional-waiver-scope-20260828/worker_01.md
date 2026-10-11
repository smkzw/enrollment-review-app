Trellis SessionStart 已加载。正在读取执行上下文并审查 `protocol_control_gate.py` 中的条件豁免绑定问题。
运行现有聚焦测试以收集当前行为证据。
# Execution Output: phase5-slice61ag-conditional-waiver-scope-20260828 - worker_01

## Boundary And Context Check

- **Role:** `worker_01` / `cursor-cli` / bounded first-line executor; no execution manager.
- **Scope:** Review only `app/protocols/protocol_control_gate.py` for conditional waiver binding, evidence modality, and cross-candidate scope. Propose minimal generic fixes and counterexample tests. No clinical source edits, no model runs, no control-point publication, no final acceptance.
- **Initial read set consumed:** `context/phase5-slice61ag-conditional-waiver-scope-20260828_execution_context.md`, `plans/codex_execution_phase5-slice61ag-conditional-waiver-scope-20260828.md`.
- **Additional reads (justified):** `protocol_control_gate.py` (regex + three check functions + publication entry), `test_slice61ab_candidate_repartition_contract.py`, checkpoint `CHECKPOINT_20260828_VIROLOGY_WAIVER_REASSESSMENT_PAUSED.md`, conference note `general_grok46.md` (read-only cross-check, not used as instructions).
- **Out of scope (worker_02/03):** `protocol_control_deconstructor.py` repair identity, v6 p804 clinical replay, immutable reassessment JSON.
- **Code hash verified:** `protocol_control_gate.py` = `a6cedc9bf267b2ee380d9983f5061788e35a829186a4fd1b4b820cc007ead4c6` (matches checkpoint).

---

## Work Performed

Independent audit of three gate mechanisms and their interaction after `MIXED_DECISION_STAGE_CONTROL`-authorized candidate repartition.

### 1. Conditional exemption binding (`_check_conditional_exemption_binding`)

**Evidence — what it does today:**

```1757:1806:app/protocols/protocol_control_gate.py
def _check_conditional_exemption_binding(
    *,
    entity_id: str,
    units: Sequence[ProtocolStructureUnit],
    trigger_expression: object | None,
    obligation_expression: object,
) -> None:
    """Keep a source condition attached to the operation it exempts."""
    conditional_source_spans = {
        span_id
        for unit in units
        if _CONDITIONAL_EXEMPTION_SOURCE_RE.search(str(unit.excerpt))
        for span_id in unit.source_span_ids
    }
    ...
            if (
                conditional_spans
                and _EXEMPTION_MODALITY_RE.search(atom_text)
                and not conditional_spans & (trigger_spans | timed_spans)
            ):
                _fail(
                    "CONDITIONAL_EXEMPTION_BINDING_MISSING",
                    ...
                )
```

**Findings:**

| Finding | Type | Detail |
|---|---|---|
| Intra-candidate binding works | Evidence | Existing tests pass; combined atom without `time_constraint` correctly raises `CONDITIONAL_EXEMPTION_BINDING_MISSING`. |
| Per-candidate scope only | Evidence | Called from `_validate_candidate` / `_validate_control` with that entity's `units` only; no batch-level sibling awareness. |
| Source detector gap | Evidence | `_CONDITIONAL_EXEMPTION_SOURCE_RE` requires `[,，；;]` between condition and exemption. Period-separated clauses (`…结果。筛选期…无需…`) do **not** match (verified by inline script). |
| Post-split false negative | Evidence + inference | After repartition, screening sibling has no exemption atom → check returns early (`conditional_spans` empty for that candidate's obligation atoms). Waiver condition lives only in sibling. |

### 2. Evidence modality (`_check_exemption_evidence_modality`)

**Evidence — what it does today:**

```1809:1838:app/protocols/protocol_control_gate.py
def _check_exemption_evidence_modality(...):
    """An optional waiver needs proof of eligibility, not proof of non-action."""
    has_exemption = any(_EXEMPTION_MODALITY_RE.search(...) for atom in ...)
    if has_exemption and any(
        _EXEMPTION_NONOCCURRENCE_EVIDENCE_RE.search(str(getattr(item, "description", "")))
        for item in evidence
    ):
        _fail("EXEMPTION_EVIDENCE_OVERSTATED", ...)
```

**Findings:**

| Finding | Type | Detail |
|---|---|---|
| Core pattern works | Evidence | `test_exemption_evidence_cannot_require_the_waived_action_not_to_occur` passes for `未/没有…再次/重复…检查`. |
| Regex too narrow | Evidence | `_EXEMPTION_NONOCCURRENCE_EVIDENCE_RE` misses: `确认筛选期未做病毒学检查`, `未重新执行…`, `未再行检查`, `no repeat virology testing at screening` (all return `False` in demo). |
| Gated on sibling obligation | Evidence | `has_exemption` requires exemption token in **same** candidate's obligation. Screening sibling with `确认三项新增检查已完成` never enters check → v6 Control 3 pattern passes gate. |
| Checkpoint alignment | Inference | Checkpoint item 3 (expand variants, only when source contains waiver) is partially done; variant coverage incomplete. |

### 3. Cross-candidate scope (missing)

**Evidence — publication loop:**

```3815:3826:app/protocols/protocol_control_gate.py
    if all_candidates:
        for candidate in all_candidates:
            _validate_candidate(...)
```

**Evidence — only batch-level sibling check today:** `_check_exception_sibling_locality` (exception fingerprint copying), not waiver scope.

**Highest-impact defect (reproducible, project-neutral):**

1. Source unit contains conditional waiver cue (`可接受…28天…，…无需再次检查`).
2. `MIXED_DECISION_STAGE_CONTROL` forces split into:
   - **Sibling A:** unanchored `complete_or_verify` “完成…检查” at screening.
   - **Sibling B:** `verify_result_validity` + exemption atom with timed anchor.
3. Each sibling passes per-candidate gates independently (demo script confirmed).
4. Clinical effect: waiver becomes unconditional screening execution on sibling A — same failure mode as v6 p804, relocated across candidates.

**Inference:** `MIXED_DECISION_STAGE_CONTROL` is necessary but insufficient for conditional-exemption sources; it authorizes split without preserving cross-candidate waiver invariant.

---

## Artifacts And Evidence

### Source files reviewed

| File | Relevance |
|---|---|
| `app/protocols/protocol_control_gate.py` | Primary audit target; hash `a6cedc9b…` |
| `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py` | Existing intra-candidate tests |
| `.trellis/tasks/…/CHECKPOINT_20260828_VIROLOGY_WAIVER_REASSESSMENT_PAUSED.md` | Proposed `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` (not yet implemented) |

### Existing test coverage (passes)

6/6 focused tests in `test_slice61ab_candidate_repartition_contract.py` (`conditional_exemption*`, `exemption_evidence*`, `planning_freezes*`).

### Gap demonstrated (inline verification, not committed)

```
MIXED_DECISION_STAGE_CONTROL: NOT raised on screening-only sibling (GAP)
CONDITIONAL_EXEMPTION_BINDING: NOT raised on screening sibling (GAP)
BINDING: waiver candidate with validity+exemption passes (expected)
NONOCCURRENCE_RE match=False '确认筛选期未做病毒学检查'
NONOCCURRENCE_RE match=False '未重新执行病毒学检查'
...
EXEMPTION_EVIDENCE: screening complete evidence not flagged (GAP)
SOURCE_RE match=False for period-separated clause
COMBINED_ATOM: correctly raises CONDITIONAL_EXEMPTION_BINDING_MISSING
```

### Proposed minimal generic fixes (recommendation, not implemented)

**Fix A — New catalog-level check `_check_conditional_exemption_scope_split`**

- **Where:** `validate_protocol_control_publication`, after per-candidate `_validate_candidate`, before `_check_exception_sibling_locality`; also aggregate published `controls` sharing source units.
- **Trigger:** Structure unit excerpt matches `_CONDITIONAL_EXEMPTION_SOURCE_RE` (after Fix C widening).
- **Invariant:** For all entities sharing that unit's span closure:
  - If any entity carries exemption modality on spans from that unit, then
  - No sibling entity may declare unanchored routine `complete_or_verify` / `perform_*` obligations on overlapping spans **unless** that sibling also carries a qualifying validity window (`verify_result_validity` with future anchor) or explicit exemption modality covering the same waived action family.
- **Error code:** `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`
- **Message (zh):** `同源条件豁免不得拆成兄弟候选中的无条件执行义务；被豁免操作须与有效期/豁免条件保持同一来源语义闭包`
- **Size estimate:** ~60–90 lines + helper to collect obligation signatures per entity.

**Fix B — Widen `_EXEMPTION_NONOCCURRENCE_EVIDENCE_RE`**

Minimal additive alternation (keep existing pattern):

```python
_EXEMPTION_NONOCCURRENCE_EVIDENCE_RE = re.compile(
    r"(?:"
    r"未|没有)[^。；\n]{0,12}(?:再次|重复|重新|再行)[^。；\n]{0,24}(?:检查|检测|执行|操作|处置)|"
    r"(?:无|未)(?:重复|再次)[^。；\n]{0,24}(?:检查|检测|执行)|"
    r"(?:未做|没有做|未进行)[^。；\n]{0,24}(?:检查|检测|执行)|"
    r"\b(?:no\s+repeat|did\s+not\s+repeat|without\s+repeat)\b[^。；\n]{0,32}"
    r"(?:test|check|exam|virology|assessment)?",
    re.IGNORECASE,
)
```

Gate only when source unit has exemption cue (move `has_exemption` to also consider source units in scope, not only same-candidate obligation atoms) — prevents global false positives on non-waiver controls.

**Fix C — Widen `_CONDITIONAL_EXEMPTION_SOURCE_RE` separator**

Allow `。` as clause boundary (or reuse `_STRONG_CLAUSE_BOUNDARY_RE` split + per-clause pairing):

```python
# Option: treat 。 like ,，；;
r"(?:若|如|如果|当|符合|满足|可接受)[^。；\n]{0,160}[,，；;。][^。；\n]{0,48}(?:无需|...)"
```

**Fix D — Combined-atom guard (optional, small)**

In `_check_conditional_exemption_binding`, if single atom matches both `_ROUTINE_ACTION_RE` and `_EXEMPTION_MODALITY_RE` on conditional spans, require same-group timed atom or trigger branch — already mostly covered; only needed if Fix A uses entity-level aggregation.

**Deconstructor repair hint (for Codex/worker_02):** Add `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` branch in `protocol_control_deconstructor.py` repair prompt builder (mirror `CONDITIONAL_EXEMPTION_BINDING_MISSING` wording but emphasize sibling candidates).

### Proposed counterexample tests (add to `test_slice61ab_candidate_repartition_contract.py` or new `test_slice61ag_conditional_waiver_scope_gate.py`)

| Test name | Expectation |
|---|---|
| `test_conditional_exemption_scope_split_rejects_screening_complete_sibling` | Two synthetic candidates sharing `su-02` with waiver source; screening-only `complete_or_verify` + validity sibling → `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` |
| `test_conditional_exemption_scope_split_accepts_validity_plus_exemption_pair` | Validity+waiver candidate alone, or properly scoped pair where screening sibling has no routine complete on waived panel |
| `test_exemption_nonoccurrence_evidence_rejects_weixingxing_and_weizhongxin` | Parametrize `未重新执行…`, `未再行检查`, `确认筛选期未做…` → `EXEMPTION_EVIDENCE_OVERSTATED` when source has waiver |
| `test_exemption_nonoccurrence_evidence_ignores_non_waiver_source` | Same evidence strings on control without waiver source → no error |
| `test_conditional_exemption_source_re_matches_period_separated_clause` | Unit test for regex / binding on `…结果。筛选期…无需…` |
| `test_validate_publication_catches_v6_like_split` | End-to-end `validate_protocol_control_publication` with 2 candidates + 2 controls mimicking v6 split shape → reject |

All fixtures must use generic synthetic excerpts (as existing 61ab tests), not D001 clinical text.

---

## Commands And Observations

| Command | Result |
|---|---|
| `pytest tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py -k "conditional_exemption or exemption_evidence or planning_freezes"` (system Python) | **Blocked** — `ModuleNotFoundError: sqlalchemy` |
| Same via parent venv `…/enrollment-review-app/.venv/bin/python` | **6 passed** in 0.02s |
| Inline gap-demonstration script (parent venv) | Confirmed cross-candidate false negatives + regex holes |
| `shasum -a 256 app/protocols/protocol_control_gate.py` | Matches checkpoint hash |

**Observation:** Intra-candidate gates are implemented and tested; the v6 failure mode is a **composition gap** after authorized repartition, not absence of `_check_conditional_exemption_binding` itself.

**Observation:** `_validate_control` omits `_check_conditional_branch_mapping` present in `_validate_candidate` — minor asymmetry, not root cause of waiver split.

---

## Blockers Or Missing Environment

1. **Default shell Python** lacks project deps (`sqlalchemy`). Tests require parent repo venv: `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.venv/bin/python`.
2. **No code edits authorized** in this worker assignment — fixes and tests are proposals only; implementation awaits Codex dispatch.
3. **Full `tests/v2/protocols` regression** not run (checkpoint notes prior 975-pass run is stale relative to latest deconstructor changes).

---

## Rerun Requests Or Next Step

**For Codex (implementation pass):**

1. Implement **Fix A** (`CONDITIONAL_EXEMPTION_SCOPE_SPLIT`) at publication boundary — highest priority; closes v6 p804-class defect generically.
2. Implement **Fix B + C** (evidence regex + source regex widening) with source-gated activation per checkpoint item 3.
3. Add six counterexample tests listed above; run focused then full `tests/v2/protocols` via parent venv.
4. Wire repair prompt for new error code in deconstructor (worker_02 scope).
5. Worker_03: v6 p804 immutable reassessment + confirm new gate rejects v6-shaped artifact.

**Question for Codex:** Should `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` fire on **candidate draft validation** (pre-publication, during runner hydration) in addition to catalog publication, so the Agent gets a repair prompt before MIXED repartition is finalized? Recommendation: yes — call same helper from hydration validator path to shorten repair loop.

**Resume point:** Implementation can start at `protocol_control_gate.py` ~line 3868 (before `_check_exception_sibling_locality`) with new `_check_conditional_exemption_scope_split(candidates, controls, unit_by_id)` and tests in `test_slice61ab…` or dedicated `test_slice61ag…` file.
