Delegated fallback is in effect: `pi` / `cursor` / `cursor-grok-4.6`. I will keep the same bounded source-only review, not claim Codex authority, and start from the assigned context and plan.Context and plan are in. Next I’ll read the listed source-of-truth files in full and check git diffs for the repeat-source increment.The glob hits are mixed with recovery artifacts. I’ll read the live contract files in full and use git to isolate this increment.`repeat_scheme.py` is untracked and simpler than the rejected-worker copy. I’ll read the remaining contracts and the dual deconstructor wiring next.The workspace grep tool missed hits I already saw in the files, so I’ll switch to `rg` and keep reading the producers and consumers.# Conference Output: r05-retest-source-review-20260915 - evidence_single_object

**Fallback / capability:** This pass ran as declared `pi` fallback `cursor` / `cursor-grok-4.6`, not the primary `grok-build` / `grok-4.6` route. Source-only review: read/search/stat/git diff only; no writes, tests, application imports, DB, model calls, or network. Exact provider JSON-schema expansion and live capture/runtime behavior are therefore **UNVERIFIED**. Codex remains final authority.

## Output

### Verdict (source capture vs pending runtime / clinical)

| Check | Status | Why |
|---|---|---|
| Domain source contract (permission / trigger / count / time / result-use / exact source) | **PASS** with gaps | `RepeatScheme` exists; dual-family producers can attach it; omitted `None` preserves old identity |
| Nullable explicit wire fields **and nested schema `$ref`** | **FAIL** (official compact wire) | Official compact atom uses `$ref` inside `anyOf`; nested duration/limit likely keep the same shape. Control family is stricter on explicit null |
| Source IDs and excerpts | **PASS** (source-level) | Pairing + substring containment on both families; official gate issue `REPEAT_SCHEME_SOURCE_UNVERIFIED` |
| Legacy serialization / hash / version | **PASS** (omitted-null identity) | `None` is stripped on dump; control eval v4 and control wire v10 are new production identities |
| Optional / no-repeat vs required / unresolved | **PASS** for no-scheme vs `permission`; **FAIL** for result-use | `repeat_scheme: null` vs object is the no-repeat split; `result_use` has no `not_specified` |
| No default chronology-based replacement | **FAIL** as a structural guard | `result_use` has no latest/best, but qualification still runs latest/earliest **before** the fail-closed reason |
| Guards on **final adoption**, not candidate arithmetic | **PASS** for this increment’s declared fail-closed | `_evaluate_atomic` / qualified selection block adoption; `evaluate_observed_value` / control operand calc do not |
| Relation proof, conditional permission, final selection | **UNVERIFIED / not implemented** | Do not treat fail-closed `repeat_relation_unverified` as a completed evaluator |
| Runtime provider capture, frozen-job mix, clinical acceptance | **UNVERIFIED** | Out of this pass; Codex owns |

**Do not treat this increment as a completed repeat evaluator.** It is a source-capture + fail-closed consumer stub. Clinical/regulatory/visual/live-web authority is not claimed.

---

### Evidence (file:line, observed)

**1. Capture contract**

```50:87:app/domain/contracts/repeat_scheme.py
class RepeatScheme(ContractModel):
    version: Literal["repeat-scheme/v1"] = "repeat-scheme/v1"
    scope: str = Field(min_length=1)
    source_span_ids: list[str] = Field(min_length=1)
    source_excerpts: list[str] = Field(min_length=1)
    permission: Literal["required", "optional", "forbidden", "investigator_discretion", "unresolved"]
    trigger: Literal["unconditional", "source_condition", "unresolved"]
    ...
    result_use: Literal["retain_initial", "use_single_repeat", "use_last_repeat", "combine", "unresolved"]
```

- Count/time distinguish `specified` / `not_specified` / `unresolved`; `result_use` does not.
- Month/year durations must be integral calendar quantities; they are not converted to days (`repeat_scheme.py:16-18`).
- `validate_repeat_source` (`repeat_scheme.py:90-96`) requires each scheme excerpt to be a substring of the **same span’s** parent excerpt.

**2. Dual-family producers**

Official compact wire:

- Prompt: every atom must emit `repeat_scheme`, including explicit `null` (`protocol_deconstructor.py:398-404`).
- Schema: field is required (`:726`) but typed as `anyOf: [$ref RepeatScheme, null]` (`:706`).
- `$defs` injection is raw Pydantic `RepeatScheme.model_json_schema()` (`:1083-1086`).
- Contrast: `observation_policy` **inlines** nested `$ref` under `anyOf` (`:640-648`) because that shape is already known to be unsafe for the provider.
- Parse: missing key is an error (`:1941`); `null` is omitted after validate, not stored as a sentinel (`:2100-2102`).

Control family:

- Prompt: scheme lives only on `evaluation.repeat_scheme`; inner `predicate.repeat_scheme` must be `null`; no-requirement is also explicit `null` (`protocol_control_deconstructor.py:1251-1254`).
- Wire gate: `evaluation.version == control-atom-evaluation/v4` **and** `"repeat_scheme" in model_fields_set` (`:471-472`, `:547-548`).
- Provider schema: `normalize_provider_schema` sets `required = list(properties)` (`:1174-1177`), so control nulls are explicit at capture.
- Hydration copies the evaluation object through (`:2451`, `:2479`).
- Versions bumped vs HEAD: control wire `v1` → `v10`, prompt `v1.6` → `v2.6`, evaluation default `v4`, publication gate `v10`, execution `v8`.

**3. Nullable dump vs explicit wire**

```41:48:app/domain/contracts/control_evaluation_spec.py
    def serialize_optional_policy(self, handler):
        value = handler(self)
        if self.observation_policy is None:
            value.pop("observation_policy", None)
        if self.repeat_scheme is None:
            value.pop("repeat_scheme", None)
```

```227:236:app/domain/contracts/rules.py
        if self.repeat_scheme is None:
            value.pop("repeat_scheme", None)
```

v4 forbids stuffing a scheme into older evaluation versions (`control_evaluation_spec.py:52-53`). Nested `predicate.repeat_scheme` is rejected on a control spec (`:73-74`).

**4. Source lineage at publication**

- Official: `deconstruction_gate.py:3358-3385` — span must be in component formal refs, excerpt in materials, excerpt in predicate clauses; issue `REPEAT_SCHEME_SOURCE_UNVERIFIED`.
- Control: `validate_repeat_source` then atom-level excerpt closure (`control_evaluation_spec.py:54, 97-102`); publication calls `validate_control_evaluations` (`protocol_control_gate.py:3986-3990`, `:4282-4286`).
- Publication does **not** re-check `model_fields_set`; explicit-null is a capture-time property only.

**5. Consumers**

Adoption fail-closed:

- `expression.py:488-489` — any present scheme → `UNKNOWN` / `repeat_relation_unverified` **before** fact matching.
- `qualified_binding_selection.py:549-551` and `:656-657` — same reason, then `if unresolved: fact_ids, pair_ids = [], []` (`:575-577`, `:682-684`).
- `assessment.py:209` maps the reason to `GapType.OBSERVATION_UNVERIFIED`.
- `reviewConditionNotes.ts:13` is presentation of that recorded reason only.

Candidate arithmetic not blocked by scheme:

- `evaluate_observed_value` (`expression.py:466-470`) — “callers own … selection”.
- `control_operand_calculation.py:59-91` — `accepted: Literal[False]`; no `repeat_scheme` check; uses `evaluate_observed_value`.

Chronology still runs first:

- `_select_with_ordering` (`qualified_binding_selection.py:311-327`) calls `select_ordered_observation` (latest/earliest) **before** the repeat guard at `:549` / `:656`.
- Semantic path may also call `_semantic_ordering` (`:531-539`, `:633-641`) before the same guard.

**6. What this increment is not**

No consumer reads `permission` / `trigger` / `time_limit` / `result_use` to prove initial↔repeat relation, conditional permission, or which result to adopt. Recovery plan text says the next item is exactly that consumer, and that chronology must not stand in for relation (`plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md` current-status bullets). Main-venue plan file is still TODO and was not used as a source of truth.

---

### Inference (separate from evidence)

**Highest-impact defect:** official compact capture can fail at the **schema** layer, before a single scheme is stored.

Concrete scenario: protocol text “实验室检查异常时可复查一次，以复查结果为准”. Compact contract wants an object with `permission=optional` or `required`, `trigger=source_condition`, `maximum_repeats=1`, `result_use=use_single_repeat`. The atom field is:

```json
"repeat_scheme": { "anyOf": [ { "$ref": "#/$defs/RepeatScheme" }, { "type": "null" } ] }
```

The same file already inlines that `anyOf`+$ref pattern for `ObservationOrdering` (`protocol_deconstructor.py:640-648`). Leaving RepeatScheme as a `$ref` inside `anyOf`, plus nested `RepeatTimeLimit | None` / `RepeatDuration | None` (Pydantic’s usual `$ref`+null shape), is the pattern this codebase has already treated as provider-unsafe. If the compact transport rejects it, **every** atom fails, including `repeat_scheme: null`. Control capture is less exposed because it already lives in a `$defs`-heavy Pydantic schema and forces every property required; official compact is the handmade schema that tried to avoid this.

**Second defect:** qualification still **computes** a chronology replacement, then discards it. Scenario: same lab, two dated values, atom has `observation_policy.selection.criterion=latest` **and** a `repeat_scheme`. `_select_with_ordering` picks the later date; then `repeat_relation_unverified` clears `fact_ids`. Final adoption is blocked (good), but “chronology is not a retest policy” is only true after the fact. A later edit that forgets the clear step would adopt latest as if it were the repeat result.

**Third defect:** `result_use` cannot distinguish “protocol silent on which result counts” from “wording present but unstructured”. Count/time can say `not_specified` vs `unresolved`. Result-use must use `unresolved` for both. That is exactly the distinction the compact prompt claims to keep (`protocol_deconstructor.py:400`).

**What is sound:** `null` vs object is the right no-repeat vs has-requirement split; `permission` carries required/optional/forbidden/discretion/unresolved; omitting `None` keeps historical predicate/eval hashes; `_evaluate_atomic` will not fall through to category/latest matching; operand arithmetic remains available with `accepted=False`; inner control predicates cannot carry a second scheme.

**Over-block by design (not a capture bug):** `permission=forbidden` or `optional` with a single observation still becomes `repeat_relation_unverified`. That is the declared gap, not an evaluator.

---

### Recommendation

1. **Block treating official compact capture as ready** until RepeatScheme has a provider schema in the same style as `_wire_observation_policy_schema` / `ObservationOrdering.provider_json_schema`:
   - inline `RepeatDuration` / `RepeatTimeLimit` / `RepeatScheme` (no `$ref` under `anyOf`);
   - atom field as `"type": ["object", "null"]` or anyOf of **inlined object** + null;
   - explicit required list including nullable `trigger_excerpt` / `maximum_repeats` / `time_limit`;
   - strip `default` / `title` if the compact transport is strict.
2. **Move the repeat guard above `_select_with_ordering` / `_semantic_ordering`** in both families; on present scheme, return empty facts + `repeat_relation_unverified` without calling `select_ordered_observation`.
3. **Add `not_specified` to `result_use`** (or an equivalent status field) so silent vs unstructured stays distinct; keep `unresolved` for wording that cannot be structured.
4. **Do not implement relation/permission/adoption in this increment.** Next work is a verified initial/repeat relation consumer that reads the captured scheme, still without defaulting to latest/best.
5. If `dnf-v5` already meant “observation_policy required” outside this bundle, **bump compact `DNF_WIRE_VERSION`**. Control wire already moved to `v10`.

---

### Uncertainty

- Exact Pydantic JSON for `Decimal` `RepeatDuration.value` (number vs string vs anyOf) was not generated; application import was forbidden. Risk: compact schema disagrees with integer `TimeQuantity` used everywhere else.
- Whether any compact transport already accepts `$ref` under `anyOf` (because `wire_time_constraint` is a whole-property `$ref`, not inside `anyOf`) is runtime-UNVERIFIED.
- Whether in-flight `dnf-v5` payloads exist without `repeat_scheme` is UNVERIFIED vs this uncommitted bundle (HEAD has no `DNF_WIRE_VERSION` at all).
- Dump → re-validate of control **wire** after `repeat_scheme: null` is popped would fail `model_fields_set`; parse-from-provider does not take that path. Repair/fingerprint uses dump for identity only.
- `GapType.OBSERVATION_UNVERIFIED` collapses the repeat reason at the gate-type layer; the UI reason string remains specific.
- Mixed-unit `time_limit` bounds are not compared (`repeat_scheme.py:41-46` only when units match).

---

### Objections to the current plan-as-implemented

1. “Source contract + fail-closed is enough to ship capture” — **not for official compact**, until nested schema refs are inlined. Capture that cannot be emitted is not capture.
2. “Fail-closed after latest-selection is the same as not using chronology” — it is not; chronology still runs and is only discarded.
3. “`unresolved` on `result_use` covers silent protocols” — it erases a distinction the prompt itself requires.
4. The main-venue plan is still TODO; the conference context, not that plan, was the source packet.

### Proposed solutions (concrete)

- Add `RepeatScheme.provider_json_schema()` and use it in `_omlx_wire_schema` the same way ObservationOrdering is sanitized; stop calling raw `model_json_schema()` into `$defs`.
- In `qualified_binding_selection`, `if predicate.repeat_scheme is not None` / `if spec.repeat_scheme is not None` **before** `_select_with_ordering`.
- Extend `result_use` with `not_specified`; keep validators that forbid inventing `use_last_repeat` / `combine`.

### Decision points for Codex

1. Is official compact transport known to reject `$ref` in `anyOf`? If yes, finding 1 is a capture blocker, not style.
2. Must `dnf-v5` be bumped, or is v5 still unpublished with observation_policy + repeat_scheme as one bundle?
3. Is over-blocking `optional`/`forbidden` until a relation consumer exists an accepted product behavior? (I would keep it.)

### Bounded questions for Codex

1. Has any compact provider session already succeeded with `dnf-v5` **without** required `repeat_scheme`? If yes, bump the wire version before capture retry.
2. Should control persist keep explicit `"repeat_scheme": null` on v4 (identity change) or keep omitting it (current, historical-safe)?
3. For the next consumer: is `use_last_repeat` “last **repeat** after a proven trigger”, not “latest observation”? The name will collide with `observation_policy.selection=latest` if that is not written into the evaluator spec.

### Required next work (declared gaps — not done)

- Initial/repeat **relation proof** (identity of the two observations, not date sort).
- **Conditional permission** evaluation (trigger true/false/unresolved; investigator discretion is not proved by dates, signatures, or counts).
- **Final result selection** from `result_use`, only after relation + permission; no default latest/best.
- Runtime/provider capture retry after schema inline; then isolated evaluation; clinical acceptance remains Codex-owned.

### Safe provisional path

Treat the domain model and fail-closed adoption stub as **source-reviewable but not capture-complete** on the official compact path. Do not run tests or mark clinical acceptance. If Codex needs a same-session follow-up, the resume point is: inline RepeatScheme provider schema + move the selection guard above chronology; re-read those two sites only.
