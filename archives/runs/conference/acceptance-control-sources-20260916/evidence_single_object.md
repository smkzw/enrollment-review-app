Trellis SessionStart context loaded. Starting the read-only evidence review.

# Conference Output: acceptance-control-sources-20260916 - evidence_single_object

## Output

### 0. Verdict (one paragraph)

The frozen patch is directionally correct, narrow, and structurally safe on the two properties the objective names first: (a) the Schema-required local `predicate_id` exemption is position-exact and cannot authorize formal IDs elsewhere; (b) quote-glyph restoration provably cannot change values, dates, units, comparators, statements, or propositions, and cannot broaden the declared source scope. It is **not complete**: three nested *explicit source fields* are still unrestored, so the exact D001-class failure (`straight quote` output vs `curved quote` frozen source) can still occur — it now surfaces under different error codes at the domain/publication layer instead of `FABRICATED_EXCERPT`. Highest-impact defect is **D1** (half-life evidence + occurrence-window/scope + repeat-role excerpts). Secondary: no audit marker for restoration (**D2**), pre-restoration dedup fingerprints (**D3**), unconstrained local-label namespace (**D4**), and weak evidence binding of the acceptance claim (**D5** — the supplied 2-line log cannot be bound to this patch; `artifacts/acceptance-20260916/full-suite.xml` exists but was outside the frozen read set).

All statements below are labeled: **OBS** = observed in file, **INF** = inference, **REC** = recommendation, **UNV** = unverified.

---

### 1. Read-set disclosure and method

Read directly per the frozen list: `app/agents/control_excerpt_restoration.py` (full), `app/agents/protocol_control_deconstructor.py` (lines 23–143, 341–345, 416–620, 655–700, 832–932, 933–1012, 1540–1610, 2050–2230, 2334–2700, 2695–2815, 2982–3012, 3549–3708), `app/domain/contracts/control_evaluation_spec.py` (full), the four test files named in the read set, and `artifacts/acceptance-20260916/control-sources-regression.log` (full, 3 lines).

Out-of-frozen-set reads I judged necessary to verify the objective's propagation claim (disclosed explicitly; no clinical/protocol/subject material, no model runs, no writes):
`app/domain/contracts/rules.py` (TimeConstraint/AtomicPredicate/FrequencyHorizon/OccurrenceWindow/repeat validators), `app/domain/contracts/common.py`, `repeat_scheme.py`, `half_life_evidence.py`, `control_evidence_policy.py`, `control_evidence_dependency.py`, `observation_selection.py` (grep), `protocol_controls.py` (validation + hydration regions), `app/protocols/protocol_control_gate.py` (two regions: 1860–1920, 2660–2770), plus greps only in `expression.py`, `gates/assessment.py`, `control_layer_evaluation.py`, `services/*`. Two bounded `Glob` calls (artifact directory listings only). **No file was modified; I did not write the runner-managed report path.**

**Tool limitation (UNV):** `Bash` was denied in this session (`permission prompts are not available in non-interactive mode`), so I could not run pytest. All test-related statements are static reading or restatements of the provided log.

---

### 2. Verified claims (with evidence)

**V1 — `predicate_id` exemption is position-exact; no formal ID is authorized elsewhere. OBS.**
`protocol_control_deconstructor.py:882-889`: the exemption fires only when `key == "predicate_id"` **and** `re.fullmatch` matches the *containing object's* path against `candidate_drafts\[\d+\]\.(?:applicability|trigger|obligation|exception)_expression|repeat_trigger_conditions\[\d+\]\.expression)\.groups\[\d+\]\.atoms\[\d+\]\.evaluation\.predicate`. `fullmatch` anchors both ends, so any deeper nesting (`….predicate.predicate_id` is the key path, container must end exactly at `.evaluation.predicate`) or any prefix (e.g. `x.y.candidate_drafts[0]…`) fails the match. Root/candidate/atom placements remain rejected as `PROVIDER_ID_FORBIDDEN` (`_FORBIDDEN_PROVIDER_KEYS` still contains `predicate_id`, `atom_id`, `candidate_id`, `condition_atom_id`, `obligation_id`, `evidence_key`, `relation_id`, `node_id`, …). Tests `tests/v2/protocols/test_control_wire_local_predicate.py:32-54` cover exactly this boundary (all four layers + repeat_trigger allowed; root/candidate/atom forbidden; `atom_id` forbidden even at the exempt path).
Path-spoofing via provider-controlled key names (a key literally named `evaluation.predicate`) is neutralized in practice: the scan runs on raw JSON (`:914-931`) but `ContractModel` is `extra="forbid"` (`app/domain/contracts/common.py:12`), so any payload needing a dotted key fails `WIRE_SCHEMA_INVALID` at `:933`. **INF** (defense-in-depth argument, not a test), see D4(ii).

**V2 — Glyph restoration cannot rewrite values/dates/units/comparators/whitespace. OBS + INF (structural proof).**
`control_excerpt_restoration.py:5`: `str.maketrans({"‘":"'","’":"'","“":'"',"”":'"'})` — a 4-entry **1:1 single-character** map. Therefore `len(normalize(x)) == len(x)`, so the index found in the normalized source is valid in the frozen source, and `matches.append(source[start:start+len(excerpt)])` (`:22`) copies **from the frozen source**. Two normalized-equal characters can differ only if both are in the same pair class (`‘/’`, `“/”`), so a restored excerpt can differ from the provider excerpt **only at those four glyphs** — never at digits, letters, units, comparators (`≥ ≤ > < = ≠`), Chinese punctuation, or whitespace (all asserted non-restorable by `test_slice61au…:300-348` and `:488-492`).
Field-level: `_restore_atom` assigns only `atom.source_excerpts` and `atom.evaluation` (`:2104-2109`); evidence path assigns only `evidence.source_policy` (`:2127-2130`). `statement`, `kind`, `modality`, `temporal_scope`, `time_constraint`, `prospective_period`, `value`, `unit`, `comparator`, `dates`, `proposition`, `semantic_proposition`, `title`, `applicable_population`, `review_node_bindings`, `atom_refs` are never assigned. Note `proposition` is deliberately unrestored and is **not** verbatim-constrained anywhere (test `tests/v2/agents/test_control_excerpt_restoration.py:23` asserts it), and `semantic_proposition` is a meaning proposition, not a source fragment (`rules.py:379-403`) — leaving both alone is correct, not a gap.

**V3 — No source-scope broadening (spans, units, or sibling borrow). OBS.**
Restoration sources are the candidate's own declared units only: `_candidate_source_texts(batch, candidate.source_structure_unit_ids)` (`:2062-2073`) filters to `candidate_unit_ids` and reads `unit.excerpt` per `source_span_ids`. Ordering is safe: candidate unit/span/closure checks run at `:2441-2466`, restoration at `:2492`. Unknown span → `sources.get(span, ())` is empty → excerpt returned unchanged → the post-restoration strict loop raises `SOURCE_SCOPE_ESCAPE` / `FABRICATED_EXCERPT` (`:2137-2166`). Descendants can only use their containing object's declared sources, and the child scope is **replaced** by the child's own restored pairs (`control_excerpt_restoration.py:39-47` with docstring `:28-32`), i.e. narrowing, never widening; the sibling-borrow case is asserted unchanged by `test_control_excerpt_restoration.py:32-38` and ambiguity is refused (`:41-43`, multi-match tests `test_slice61au…:271-294`). Descendant `source_clause(s)` may match any of the parent atom's own excerpts (flattened `texts`, `:47`) — this is exactly the containment rule the spec validator enforces (`control_evaluation_spec.py:83-87`), so it is consistent, not loose.

**V4 — Model validation still rejects unsupported source changes. OBS.** Non-quote differences, ambiguity, span mismatch, digit/unit/comparator differences all still raise (`test_slice61au…:271-348`, `:355-433`); `validate_control_atom_evaluation` still enforces spec-excerpt ⊆ atom-excerpt and policy-excerpt ⊆ atom-excerpt (`control_evaluation_spec.py:101-123`).

**V5 — Raw response hash retained by the runner; caller wire not mutated. OBS.** `validate_protocol_control_agent_wire` works on `wire.model_copy(deep=True)` (`:2364-2366`), so `hydrate_protocol_control_agent_output(wire_obj, …)` cannot mutate the caller's object (`test_slice61au…:243-247`). The runner hashes the **raw text**: `raw_output_sha256=_sha256(raw_text)` on success (`:3662`) and on failure (`:3689`), never the restored copy; `test_slice61au…:440-481` and `:534-549` assert this against a recorded `text_sha256`.

**V6 — Old wire is not upgraded to v23. OBS.** `wire_version: Literal[CONTROL_AGENT_WIRE_VERSION]` (`:809`), plus the explicit gate at `:2642-2646`; `CONTROL_AGENT_WIRE_VERSION = "phase5/control-agent-wire/v23"` is the only production value (older `v1`/`v9` literals exist only inside `artifacts/recovery-*` and `artifacts/phase55-*` snapshot copies, which are not on the `app` package path). I found **no** migration/normalizer/rewrite of `wire_version` anywhere in `app/`. The historical replay asserts rejection (`test_slice61au…:530-532`) and the runner returns `需要核对` with the raw hash retained (`:544-549`). Wire-side `repeat_scheme` presence is still required explicitly (`:448`, `:526`), and evaluation `version` is pinned to v4 there, so a v4 spec cannot absorb a legacy evaluation shape.

---

### 3. Defects

#### D1 (highest impact) — Restoration coverage is incomplete at three nested explicit-source positions; the D001-class failure can still occur

**D1 scope.** `restore_source_fields` only restores (i) paired `source_span_ids` + `source_excerpts` in the same dict, (ii) `source_clause`, (iii) `source_clauses` (`control_excerpt_restoration.py:38-53`). `_restore_atom` additionally restores only `atom.evaluation` and the evidence `source_policy` — **never `atom.time_constraint`** (`:2094-2130`).

**D1(a) `HalfLifeEvidence` — highest severity, concrete publication failure. OBS + INF.**
`half_life_evidence.py:15-16` uses **singular** `source_span_id` / `source_excerpt` — never eligible for the paired branch and not a clause key. The publication gate then requires verbatim containment **in the restored atom excerpt**:
`app/protocols/protocol_control_gate.py:1885-1891` — `evidence.source_span_id == span_id and evidence.source_excerpt in excerpt and evidence.applies_to_quote in excerpt`, else `HALF_LIFE_SOURCE_UNVERIFIED`.
Path: source text has `…’s…` (exact D001 pattern; `half_life_evidence.py:50-51` even anticipates the `'s`/`’s` suffix); provider emits straight quotes consistently → atom `source_excerpts` restored to curved → passes `FABRICATED_EXCERPT`; `half_life_evidence.source_excerpt` stays straight → gate fails → `publication_invalid` → consumes the bounded repair budget (`max_schema_repairs=2`) → `需要核对`. Reachability requires a model-supplied half-life window (`half_life_multiplier` + evidence) with a quote glyph in the same sentence — real but narrower than the D001 ECG case.
**Minimal fix (REC):** prefer extending deterministic restoration to `atom.time_constraint` (and `evidence.source_policy.result_validity_constraint`) and add a **singular** `source_span_id`/`source_excerpt` pair case to `restore_source_fields`, scoped to the atom's own restored excerpts (same uniqueness rule). Rationale: keeps one canonical, glyph-correct representation in the frozen artifact; a gate-side normalization-only fix leaves the same sentence stored twice with two different glyphs, which is worse for audit. If Codex prefers minimal blast radius, the alternative is to compare with `control_quote_normalize` on both sides inside `_check_atom_sources`. Either way, add a regression test mirroring `test_slice61au…` for the half-life path — no reviewed test covers it.

**D1(b) `AtomicPredicate.occurrence_window.scope` / `.horizon.source_excerpts` — domain rejection after restoration. OBS.**
`rules.py:355-361` requires each `horizon/scope.source_excerpts` entry to appear inside `predicate.exact_source_clauses` (which **is** restored). Those lists are unpaired (no `source_span_ids` sibling), so they stay straight while the clause becomes curved → `多期间统计范围须属于本条件逐字原文` / `频次期间依据须保留在本条件逐字原文内`. Failure surfaces at `ControlAtomEvaluationSpec.model_validate(evaluation_payload)` inside `_restore_atom` (`:2103`) → caught by `wire_to_protocol_control_batch_disposition` (`:2647-2692`) as `DOMAIN_DRAFT_INVALID`. Reachable for deterministic frequency windows (e.g. `≥2次` with a quoted condition) — common structurally, requires a glyph inside the cited fragment.

**D1(c) `RepeatEvidenceRole.source_excerpts` / `RepeatMultiInitialPolicy.source_excerpts` — post-hydration rejection. OBS.**
Both are unpaired (`repeat_scheme.py:13`, `:96`). Domain check `protocol_controls.py:1286-1288` requires each role quote to be inside the **scheme's** `source_excerpts` (restored) → `复查取证范围须来自本项复查要求的方案原文`. The same rule runs on the wire *before* restoration (`protocol_control_deconstructor.py:702` → `:1255-1303`) and passes then; the failure appears only after hydration (`protocol_controls.py:1332/1473/1762` re-run it on hydrated controls) → `HYDRATION_INVALID`, i.e. a *different, harder-to-diagnose* error for a glyph-only difference.

**D1 framing (important, to avoid overclaiming):** this is **not a regression** — before the patch all three positions also failed, but earlier (at `FABRICATED_EXCERPT`). The patch narrows the failure surface without closing it, so metrics/error-code comparisons can show "new/other failures" while the root cause persists. Recommend recording this as a documented limitation with a test, or closing it via the D1(a) fix applied uniformly.

#### D2 — No audit marker that glyph restoration occurred (Medium, OBS)
`ProtocolControlAgentAttempt` (`:2982-2996`) has `raw_output_sha256`, `outcome`, `issues`, … but nothing records glyph restoration; the runner only notes the *bounded repair* case (`:3665-3669`). Result: the frozen control artifact stores curved-quote excerpts while the raw response (and its hash) is straight-quote text, with no recorded reason. An auditor diffing artifact vs raw response sees unexplained divergence; `_restore_atom` already knows when it changed something (`:2104`).
**Minimal fix (REC):** append a bounded, machine-readable note to `attempts[i].issues` (e.g. "字形还原：N 处引号，原文哈希保留") using the existing mechanism. Cheap, non-behavioural, directly serves the project's evidence-traceability boundary.

#### D3 — Duplicate detection runs on pre-restoration text (Low, OBS)
`DUPLICATE_CANDIDATE` fingerprint is computed before restoration (`:2467-2475`; `_validate_exact_atom_sources` runs at `:2492`), and wire-level DNF dedup likewise runs at parse time (`:500-507`, `:592-599`). Two entries differing only in quote glyphs pass dedup but become byte-identical after restoration, so the persisted artifact can contain duplicates the dedup invariant was meant to forbid. Low likelihood (requires a provider emitting near-duplicates differing only in quotes). **Fix (REC):** recompute the fingerprint on the post-restoration dump (or dedup on the restored representation).

#### D4 — Two label/hardening items (Low, OBS + INF)
(i) The local `predicate_id` is any non-empty string, is **not** uniqueness-checked, and is persisted into the frozen control artifact. I verified nothing in the control path consumes it as a key: control atoms carry `.evaluation` (not `.predicate`), and `protocol_control_gate.py` / `app/domain/control_layer_evaluation.py` contain no `evaluation.predicate` or `predicate_id` usage at all (grep, no matches). All `predicate.predicate_id` consumers are the **rule** path, where IDs are system-assigned (`protocol_deconstructor.py:2302`, `:2424`) and uniqueness is enforced (`rules.py:569-573`). So the residual risk is *confusability in the artifact* (a reviewer or export could read `predicate_id: "IN-01"` or `pca-…` as an official/system identity), not a key collision.
**Fix (REC):** constrain the local label (e.g. `^[a-z][a-z0-9_-]{0,63}$`) and reject reserved/forged forms — the project already applies exactly this precedent to relation targets (`:653-657` with `is_forbidden_protocol_control_code`, `protocol_controls.py:266-269`; reserved system prefixes `pca-`/`peg-` at `protocol_controls.py:2877`, `:2900`). Extend the same guard to the provider-chosen `condition_id`, which is likewise outside `_FORBIDDEN_PROVIDER_KEYS` and unconstrained.
(ii) `_find_forbidden_provider_key` builds its path by concatenating **unescaped provider key names** (`:891`, `:896`), so the allow-list is string-path-based rather than structure-based. Currently unexploitable thanks to `extra="forbid"` (V1), but the check's correctness depends on that coupling. **Hardening (REC):** reject keys containing `.`/`[`/`]`, or re-scan the validated `model_dump(mode="json")` instead of raw JSON. (Deliberately reported as hardening, not a live bug.)

#### D5 — Acceptance evidence is not bound to this patch (Medium, OBS)
`artifacts/acceptance-20260916/control-sources-regression.log` contains exactly: 72 dots, 31 dots, `103 passed in 0.64s`. No command line, no commit SHA, no timestamp, no test-file list, no `-v` IDs. My static count of the four reviewed files is roughly **45–50 tests** (≈8 + 11 + 30 for the 61au file + ≈40 in 58c), so a 103-test run must have included other modules — the log therefore **cannot** be bound to the frozen patch as its own evidence. Zero skips is at least consistent with the D001 artifacts being present (that test `pytest.skip`s if missing, `:504-505`) but does not identify what ran. I observed (directory listing only, **not read** — outside the frozen read set) that `artifacts/acceptance-20260916/full-suite.xml` exists next to the log.
**REC:** bind the acceptance claim to `full-suite.xml` (or a re-run with recorded command, commit, and `-v` output) and retire/annotate the 2-line log. Separately, the conference packet itself has TODO placeholders in `context/…_conference_context.md` (Source Of Truth / Scope / Success Criteria) and `plans/codex_main_venue_…md` (Date / Task Decomposition / Source Packet / Verification Checklist) — those are the packet's declared decision sources and are currently empty.

#### D6 — No positive end-to-end evidence for the fix (Medium, OBS)
The only authentic-data test is `test_slice61au…:499-549`. It asserts: the real `body.p790` excerpt contains `Fridericia’s`; a raw response contains `Fridericia's` with a matching recorded hash; `_recover_control_excerpt` yields the curved form; the stale response's `wire_version != v23`, hydration raises `WIRE_SCHEMA_INVALID`, and the runner returns `需要核对` with the raw hash retained. By construction (test name: *"old_wire_is_not_current_acceptance"*) it does **not** produce a current-schema wire for that batch, so it does not demonstrate that a D001-shaped candidate now hydrates and publishes. **INF:** therefore `103 passed` is not clinical acceptance of the D001 control, and should not be cited as such — consistent with the objective's own warning.

---

### 4. Toy fixture vs authentic fidelity (explicit boundary)

Everything in `tests/v2/agents/test_control_excerpt_restoration.py` and `tests/v2/protocols/test_control_wire_local_predicate.py`, and 8 of 9 sections in `test_slice61au…`, is **synthetic**: hand-built `ProtocolStructureUnit`s (`su-ecg-01`, `span:ecg-01`, `pcb-61au-01`, one Chinese ECG sentence reused as a string literal), not protocol text from a real source document. They validly test the *mechanism* (glyph set, uniqueness, ambiguity, scope confinement, non-quote strictness, hash handling) and I treat those results as sound **for the mechanism only**. Only §9 touches authentic frozen artifacts, and only for one sentence plus fail-closed rejection. **UNV:** whether any real D001/61as batch produces a current-schema response that now hydrates and passes the control gate — no such post-patch artifact was in the read set, and my Glob listing (truncated at 40 entries) cannot establish absence.

---

### 5. Objections, proposed solutions, decision points, bounded questions

**O1 — The patch's stated contract and its implementation disagree on "explicit source fields".** The docstring says *"Restore quote glyphs in explicit source fields"* (`control_excerpt_restoration.py:1`), but the implementation covers only plural pairs and clause keys. Six contracts declare explicit source fields in other shapes: `HalfLifeEvidence.source_excerpt` (singular), `FrequencyHorizon.source_excerpts`, `OccurrenceScope.source_excerpts`, `RepeatEvidenceRole.source_excerpts`, `RepeatMultiInitialPolicy.source_excerpts`, `source_policy.result_validity_constraint` (nested). **Decision needed:** is the intended invariant "every verbatim-containment comparison is glyph-equivalent" or "only the declared excerpt fields are restored"? I recommend the former (fix A in D1(a)) because it yields one canonical representation in the frozen artifact and one normalizer used by every containment check (**REC**).

**O2 — Fail-closed is being achieved at the wrong layer.** D1(b)/(c) convert a glyph-only difference into a *domain/publication* rejection, which the repair prompt's `FABRICATED_EXCERPT` guidance (`:1596-1602`) no longer addresses, so the model is asked to fix something whose error text no longer mentions quotes. If partial coverage is intentional, the repair guidance should cover the nested-position codes too, or the repair budget will be spent unproductively. **Objection to the current split:** a mixed-state artifact plus a misleading error code is the worst combination for audit; prefer either full restoration or an explicit, documented "unsupported position" list.

**O3 — Acceptance evidence should be re-bound (D5/D6).** The 2-line log cannot carry the claim; `full-suite.xml` plus a post-patch D001 replay can. I did not read either (read-set boundary), so Codex owns this.

**Bounded questions for Codex (each answerable without new exploration):**
1. Intent confirmation: should glyph equivalence be enforced at *every* verbatim-containment comparison, or is restoration deliberately limited to the fields currently handled? (Determines fix A vs fix B for D1.)
2. Does a post-patch replay of the D001 ECG batch with the **current** `wire_version` exist, and at what artifact path? If not, is one scheduled before acceptance?
3. May the acceptance claim be re-bound to `artifacts/acceptance-20260916/full-suite.xml` (or a re-run with recorded command/commit), retiring the 2-line log?
4. Is provider-chosen `condition_id` (and the local `predicate_id` shape/pattern) in scope for this slice, or explicitly out of scope and deferred?
5. Are D1(b)/(c) positions accepted as known limitations for this slice (with a test pinning current behaviour), or must they be closed before acceptance?

**Provisional safe path if unanswered:** treat D1(a) as a blocker for any claim that "the D001-class typographic failure is fixed"; treat D2/D5/D6 as acceptance-artifact gaps that do not block code correctness but do block the audit claim; ship nothing to production based on this pass alone (Codex retains final authority).

---

### 6. Uncertainty / UNVERIFIED register

**UNV-1** No test execution possible (`Bash` denied); all test verdicts are static reading or the supplied log.
**UNV-2** Whether files outside the frozen read set already cover the D1 nested positions — I read the four named files and found no such case; other suites were not enumerated.
**UNV-3** Existence of a post-patch D001 replay artifact (Glob listing truncated; read set forbade inferring absence).
**UNV-4** Contents of `artifacts/acceptance-20260916/full-suite.xml` (out of read set; listing only).
**UNV-5** Whether `source_term` verbatim enforcement applies to the **control** path (I found it only in `app/protocols/deconstruction_gate.py`, the rule path). If a control-side equivalent exists, `predicate.source_term` would be a fourth unrestored position of class D1.
**UNV-6** Exact incidence of D1 on real D001/61as batches — the code path is verified; the frequency depends on real protocol text I was not permitted to read.

---

### 7. Compact evidence trail

Restoration core `control_excerpt_restoration.py:5,12-24,27-55`; restoration call sites and scope `protocol_control_deconstructor.py:2062-2073,2087-2130,2137-2166`; copy-not-mutate `:2364-2366`; version pin `:90,809,2642-2646`; identity exemptions `:847-899,914-931`; dedup `:2467-2475`; runner hashing/notes `:3549-3671,3689`; attempt model `:2982-2996`; spec validators `control_evaluation_spec.py:41-88,91-138`; half-life contract `half_life_evidence.py:12-18`; gate check `protocol_control_gate.py:1885-1891`; occurrence/scope containment `rules.py:355-361`; repeat-role containment `protocol_controls.py:1286-1288` (wire pre-restoration `protocol_control_deconstructor.py:702`); system ID prefixes `protocol_controls.py:2877,2900`; forged-code precedent `:266-269` and `protocol_control_deconstructor.py:653-657`; `extra="forbid"` `common.py:12`; tests `tests/v2/agents/test_control_excerpt_restoration.py` (full), `tests/v2/protocols/test_control_wire_local_predicate.py` (full), `tests/v2/protocols/test_slice61au_typographic_restoration.py:182-549`, `tests/v2/protocols/test_slice58c_control_deconstructor.py:127-300,638-877`; evidence log `artifacts/acceptance-20260916/control-sources-regression.log` (3 lines, unbound).

No files were created or modified; no clinical source material, subject data, or model runs were accessed; the runner-managed report path was not written.

**End of report.**
