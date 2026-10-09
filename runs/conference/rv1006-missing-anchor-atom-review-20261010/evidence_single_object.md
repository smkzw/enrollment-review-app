Trellis SessionStart context loaded.

Starting the bounded read set. First, locating the named symbols in the allowed files.

Report follows. Engineering advice only, not clinical approval.

# Independent review report — missing-anchor scoped atom recovery

Artifact: current uncommitted working-tree patch on HEAD 81b3cd0e (file contents as read; no diff/status commands used). Delivered evidence: 4 targeted greps + 4 bounded reads across the allowed five files; one additional 2000-line read attempt exceeded the platform token cap and returned no content (disclosed under Limitations). No tests, network, browser, clinical files, or writes were used.

## Findings

### F1 — Exact-identity selector: claim verified (no proven bug)
`app/agents/protocol_control_deconstructor.py:5980` `_missing_anchor_atom_repair_path`.

Verified checks, all in one function, before returning a path:
- Fresh, single finding: exact class set `{PUBLICATION_GATE_REJECTED, TIME_ANCHOR_MISSING}` (strict equality, line 5987), `len(error.validation_findings) == 1`, `len(candidate_indexes) == 1`, and explicit refusal of `repair_scope_unknown`, `allow_candidate_repartition`, `allow_source_closure_rewrite`, `allow_source_insert` (5988–5990). Conflicting error classes are excluded, not merged.
- Path shape: strict regex `/obligation_expression/groups/{g}/atoms/{a}/time_constraint` with no leading zeros (5996–6000), then indexed access guarded by `IndexError` (6007–6011).
- Wire↔hydrated binding at the same path: `atom.source_span_ids != hydrated.source_span_ids`, `atom.source_excerpts != hydrated.source_excerpts` (6017–6018), `finding.entity_id == f"{candidate.control_candidate_id}/{hydrated.obligation_id}"` (6019), candidate source units vs `frozen_structure_unit_ids` (6016, 6020), span-set equality both from the finding and from `error` (6022–6023), owner match (6003–6004), and `atom.time_constraint is not None` → refuse (6015).
- Hash parity: selector recomputes sha256 over `json.dumps(atom.source_excerpts, ensure_ascii=False, separators=(",", ":"))` (6012–6014); the producer at `app/protocols/protocol_control_gate.py:3225`–`3236` emits `source_excerpt_sha256` with the identical normalization, plus `entity_id=f"{entity_id}/{atom_id}"`, `json_path=f"{atom_path}/time_constraint"`, `structure_unit_ids`, `obligation_source_span_ids`. The two computations are congruent.

Stale findings are not possible in this flow: the selector runs in the exception handler of the same iteration that produced the error (call site `deconstructor.py:10816`–`10822`) against the same `wire`/`output` objects; nothing persists findings across rounds.

### F2 — Mutation scope: claim verified (no proven bug)
`deconstructor.py:6890` `_merge_obligation_atom_repair`, `missing_anchor_only` branch at 6948–6953 and response contract at 6914–6920.
- Payload must be exactly `{"atom": ...}` (6914); full-candidate/wire shapes are rejected outright.
- Frozen fields compared against the baseline atom: `kind, statement, modality, temporal_scope, source_span_ids, source_excerpts, requires_professional_judgment, prospective_period, continuing_obligation` (6934–6940).
- Time-only mode: original `time_constraint` must be null and replacement non-null (6949–6950); evaluation changes are limited to `time_operand_attribute`/`time_purpose` (6951–6953). Any other evaluation field change raises `ATOM_REPAIR_INVALID`.
- Single positional splice: `merged = deepcopy(baseline)`; only `groups[g].atoms[a]` is replaced (6930, 6954). All sibling atoms are byte-identical by construction. The baseline mapping itself is not mutated.

### F3 — Retry confinement and capability gap: claim verified (no proven bug)
- Exception handler saves then clears the mode (`10379`–`10390`); on the next failure it re-grants the same path and the flag **only** if `previous_missing_anchor_only and repair_baseline_raw is not None` (`10427`–`10431`). `repair_baseline_raw` can only be cleared after a *successful* parse (`8372`), at which point the flag is also cleared (`8379`); a parse-stage failure therefore always retains both. The `_invalid_candidate_payload` salvage path (which could reassign `atom_repair_path`, `10464`) cannot fire for this flow because it requires a wire-shaped payload and the baseline is a fully valid wire dump → `invalid_indexes` empty → returns `None` (`6357`–`6399`).
- Missing transport capability: `atom_only` requires `callable(transport.continue_atom)` (`11206`–`11210`); if it is absent while `missing_anchor_only` is set, the runner returns `需要核对` immediately (`11212`–`11222`) instead of falling back to candidate rewriting. This is the correct fail-closed behavior.
- Prompt and budget: the flag is passed to `_build_obligation_atom_repair_prompt` (`11405`–`11409`; scoping text at `7003`–`7009`), and the round consumes the same `repairs` counter (`11204`–`11205`) under the existing stop conditions (`11155`–`11171`, plus `no_progress` at `10419`–`10421`).

### F4 — Shared-span guard: bounded at the call site, body unverified
`bounded_atom_patch_applied` (`8369`–`8371`) is consumed at `8392`–`8395` by passing `mutable_obligation_source_span_ids=set()` to `_restore_bounded_wire_repair` **only** for merged iterations (calendar/future/atom paths); the accompanying comment (`8366`–`8368`) states the intent: a span may support independent siblings, so the already-bounded patch must not be re-identified by span. Non-merged (full-rewrite) iterations still pass the full span dictionary (`8384`–`8401`), i.e., the old ambiguous-span refusal is bypassed *for the bounded class only*, not relaxed for rewrites. That is consistent with the claim at call-site level. The body of `_restore_bounded_wire_repair` (`5049`) was not read within the delivered budget, so "the old guard is unchanged" is supported, not verified line-by-line. Note: `bounded_atom_patch_applied` covers the two pre-existing bounded modes as well; each of their merges is also a single-atom splice (`6087`–`6128`, `6237`–`6270`), so the suppression is coherent, but without a diff against 81b3cd0e I cannot confirm what behavior changed for those modes.

### F5 — Possible risk (residual semantic gap, pre-existing gate property)
Nothing in the bounded merge or in the read portion of the gate (`protocol_control_gate.py:2866`–`3259`) verifies that a newly supplied `anchor_type`/`direction` is the anchor the atom's own source text actually names. The gate checks structural legality (anchor/direction required, 2886–2889), windows/comparators/half-life/precision, and only one guess rule (`screening_date` + first-dose/randomization words, 3240–3249). A structurally legal but wrong anchor can therefore pass machine checks after this repair. Concrete dangerous example: atom source "随机化后开始治疗" repaired with `anchor_type=visit_date, direction=on` passes the read checks (no named-anchor-vs-source verification), while a source-correct answer would be `randomization_date`. This is a product boundary (AI-led, human review is the decider) and not a regression introduced by the patch; flagging so the owner accepts it deliberately rather than by accident. Smallest option if addressed: for this bounded path only, require an anchor-cue presence check against `atom.source_excerpts`, or tag the repaired atom for review — a product decision, not an obvious code fix.

### F6 — Possible risk (over-restriction — safe direction)
The selector's strict equalities (tuple equality of `error.candidate_ids`; set equality of finding/error structure units against `frozen_structure_unit_ids`; two-way span-set equality) may refuse legitimate cases when the gate populates `structure_unit_ids` from a broader caller scope (`protocol_control_gate.py:3230` passes its `structure_unit_ids` parameter; provenance at call sites 4492/4793 not read). Consequence is refusal/no repair (fail-closed), so this is availability/latency, not safety.

### F7 — Boundary clarification (not a bug under this architecture)
The time-only lock is per-error-round. If the bounded patch parses but a *different* later validation fails, the next round grants that new error's own scoped authority (e.g., duration/early-anchor selectors at `10804`–`10815`), whose contracts can legitimately change other evaluation fields of the same atom while still freezing statement/source and re-running the full publication checks (`8422`–`8452`). This matches the runner's documented "one proven scope per round, next full validation discovers what remains" design (`10400`–`10401`). If the owner's claim is read as "the atom may never receive broader authority in any subsequent round", the claim overstates the implementation; the same-error retry claim does hold (F3).

### F8 — Possible risk (very low, not proven reachable)
In the merge chain, the observation branch is evaluated before the atom branch (`8323`–`8334`). If both `observation_repair_candidate` and the atom path were set in one round, the atom response would be parsed once as an observation repair, fail, and then the observation candidate is dropped on the exception path (`10388`–`10389`) while the atom path is restored (`10430`) — transient, self-correcting. Reachability depends on the unread head of `_future_observation_scope_repair_path` (before line 5960); not demonstrated.

## Counterexamples (concrete)

- Positive (the fix works): one candidate, atom A (groups/0/atoms/0) and atom B (atoms/1) cite the same sentence and share `source_span_ids`; only B lacks `time_constraint`. Gate emits one `TIME_ANCHOR_MISSING` finding with B's path, B's obligation_id in `entity_id`, the shared span set, and the hash of B's excerpts. Selector binds wire and hydrated B at that exact path; A has a constraint (else there would be two findings → refuse) and a different obligation_id. Merge replaces only position (0,0,1); A is byte-identical; B's time fields are filled; full validator and gate re-run. The old span-dictionary restore could not be used here (ambiguous shared span) — correctly, because it is not needed.
- Dangerous, survives the patch: the wrong-but-legal anchor in F5 — no mutation leak, but a clinically wrong named anchor can pass machine checks and must be caught in human review.
- Dangerous, rejected by the patch: smuggled change — replacement atom that adds the constraint but also alters `predicate`, `observation_policy`, `statement`, `source_excerpts`, or `continuing_obligation` → frozen-field and evaluation-field loops raise (`6934`–`6953`). Full-wire response instead of `{"atom"}` → rejected at `6914`. A refused atom cannot re-open candidate-level authority on the same-error retry (F3).

## Smallest recommendation

1. Verify `_restore_bounded_wire_repair` (`5049`) accepts an empty span-id set without altering its refusal semantics for non-bounded restores; that is the one claim (F4) I could not close within the read budget.
2. Confirm the new test families pin the two properties that carry the safety argument: sibling atoms byte-identical after a duplicated-span missing-anchor repair, and a second identical failure ends in `需要核对` with no escalation. I could not read the test file (budget/truncation), so this is unverified.
3. Accept or reject F5 explicitly; do not let a structurally-legal anchor be treated as a source-proven one by default.

## Limitations

- Read budget: five allowed files, eight delivered greps/reads; one failed oversized read is included in that count but delivered no content. Not read: `app/protocols/protocol_control_repair_errors.py` (entirely), the test fixture/new families, `protocol_control_execution.py` beyond the grep hits (registration string at `2111` within `_deep_component_identity`; comparison sites at 1245/2780/4093 etc. exist — "forces current checks instead of upgrading old proofs" is a plausible inference, not verified), `_restore_bounded_wire_repair` body, `_validate_bounded_output_repair` body, and the gate's `structure_unit_ids` provenance at its call sites.
- No diff against 81b3cd0e was permitted, so "new vs. pre-existing" attributions are limited to what the current contents show.
- No tests executed; no real transport calls; synthetic trace reasoning only and not clinical acceptance. Reviewer is DeepSeek-family (program/context separation, not model independence).
