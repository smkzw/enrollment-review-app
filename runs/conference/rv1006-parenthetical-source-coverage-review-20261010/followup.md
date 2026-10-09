Trellis SessionStart context loaded. Executing the same-session follow-up under the same read-only role: one locating search plus two bounded reads, then the report as text.

Three clusters located. Executing the two remaining bounded reads (the four requested definitions cannot fit in one contiguous range; they span 161-275 and 4879-5100+).

Review complete. 3/3 calls used (1 locating search + 2 bounded reads: gate.py:150-349 and gate.py:4860-5219). Report below.

---

# Focused follow-up — SAME-candidate complete-text retention (v48)

Artifact: working-tree code (uncommitted patch on ea69c598), read-only. No tests, edits, network, or clinical access. Owner-reported connected-run results are labeled as owner-reported and were not verified by me. Nothing here is clinical acceptance; citation coverage is not meaning.

## Findings

### F1a — Mechanism verified: the retention is literal, same-candidate, same-unit, union-gapless (direct code evidence)

- Gate construction `protocol_control_gate.py:4919-4930`: `candidate_atoms` is a **list-of-lists, one list per linked candidate** (atoms from applicability/trigger/obligation/exception via `_iter_expression_atoms`). Invocation `4953-4955`: `_parenthetical_prohibitions_are_quoted(normalized_quote, atoms, unit.source_span_ids)` is called **per candidate**, and `any(...)` across candidates — pieces from different candidates can never jointly satisfy it. "No borrowing" holds by construction.
- Fragment atom requirement `226-253` unchanged: well-formed single-level parens only (231), any residual paren char → strict fallback (233), any prohibition word outside parens → fallback (235), and **every** prohibitive parenthetical must have a grounded atom (spans nonempty and ⊆ unit spans) whose statement AND an excerpt both normalize-equal the fragment (241-253). Nested (`[^（）()]+` cannot cross parens), mismatched (no match or residual), outside (235), and wrong-unit/wrong-source (244, test row `wrong_source`) all still reject.
- Retention `254-271`: ranges = one range per prohibition-match atom's fragment (through the located excerpts), plus a **1-char range for each fragment's opening and closing paren** (`256-257` — only the two paren characters, nothing inside), plus located ranges for **every `source_excerpts` entry of every grounded atom of the same candidate** (`258-264`). Statements are never used for coverage; only excerpts.
- Locator `5015-5032`: whitespace-collapse-only exact match; **returns `None` on empty target and on any multi-occurrence (ambiguous) quote** — no fuzzy, no first-occurrence guessing. Located bounds are exact frozen-text offsets.
- Merge `265-270`: sorted; merged only when `start <= merged[-1][1]` — that is exact interval union (touching/overlap); **no gap-filling, no envelope (min/max) shortcut**.
- Coverage `5059-5080`: walks sorted merged ranges; any non-space character in a gap that is not in the allowed separator set → `False`; tail after the last range must be space/separator. With `allow_joining_punctuation=True` the separator set is `；;。.:：，,` — i.e., **only punctuation may be skipped; every word character (CJK, digits, Latin) must lie inside a literally located citation range**.

### F1b — F1's counterexample is now rejected at the changed layer itself

Parenthetical-only atom (statement+excerpt = `复核前不得改变原有治疗方案`, spans on the unit; fixture form from `tests/v2/protocols/test_slice58c_protocol_control_gate.py:439-441`, read in the prior pass, not re-read this pass) against clause `筛选期发现检查异常时，允许复核（复核前不得改变原有治疗方案），结果正常后进入后续流程。`:
- The fragment atom condition passes, but retention fails: `筛选期发现检查异常时，允许复核` and `结果正常后进入后续流程` are in no located citation range, are not separators, and not exempted → `source_statement_ranges_cover_unit` `False` → helper `False` → falls through to the ordinary coverage routes (`4950-4952`) → if none apply, `ENROLLMENT_PROHIBITION_UNCOVERED` is still reported (`4993-5005`).
- Conversely, if the same candidate cites the governing run-up and the trailing context on any of its own atoms (any role), coverage passes and only then does the branch accept. This is the owner's replay behavior (first output passes the prohibition guard; a repair that detaches the governing context into a different candidate still fails) — **owner-reported**, and consistent with the per-candidate code above.

### F1c — Overlap bypass question: NO new textual-omission bypass

Answer: overlapping quotes do not introduce a new bypass relative to the old whole-sentence citation route, because (i) merge is exact union, not envelope, and (ii) acceptance still requires every non-separator character of the clause to be inside some literally located, unambiguous, same-candidate excerpt range. Attacks tested against the code and excluded:
- Gap hidden between head and tail quotes → rejected by the gap scan (`5076-5078`).
- Quote whose normalized form is empty → `None` (`5024-5026`).
- Ambiguous/duplicated quote exploited for positioning → `None` (`5029-5031`).
- Model-authored statements covering text → statements unused for coverage (`258-264`).
- Cross-candidate / cross-unit borrowing → per-candidate lists (`4919-4930`), span-subset grounding (`242-244`).
- Nested/mismatched/outside → strict fallback (`231-240`).
Remaining relaxations vs a strict single-quote path are exactly four, and none can hide a word: split citations across the same candidate's atoms; uncited separator punctuation incl. `，,`; the two paren characters per parenthetical (`256-257`); whitespace. No directly causal mandatory fix is warranted for this helper on the bypass question.

### F1d — The strongest genuine counterexample is meaning-level, not presence-level

A candidate can fully cite the clause yet attach the governing condition text to the **wrong atom role** (e.g., the run-up cited on an exception/trigger atom whose model-authored statement places or inverts the condition; the prohibition atom's statement is only the fragment). Coverage passes; role/branch equivalence is not established by citations. This is the declared boundary (`229`, comment `254-255`) — the presence helper should not become a second semantic interpreter, and citation coverage alone must not be treated as proof of meaning. Under the old route (`quoted_clauses`, `4934-4944`) the whole-sentence *quote* also was not bound to a correct statement (`statement == fragment` with a whole-sentence quote could qualify), so the attachment delta is real but narrower than it first appears. Resolution of F1d belongs to candidate-level checks (`_check_conditional_branch_mapping`, def at `2171`, **not read this pass — budget**) and the final source/semantic review, which is not waived.

### Layers, explicitly

1. **Source presence**: now strictly enforced (same candidate, same unit, whole clause, literal, union-gapless, punctuation-only exemptions).
2. **Meaning / branch equivalence**: untouched and unproven by this function; depends on candidate checks (unread here) and final review; do not overload the helper.
3. **Publication**: unchanged; not re-verified this pass. The helper alters no publication gate and provides no acceptance signal beyond the coverage diagnostic suppression.

## F1 disposition

**Clear F1 at its stated scope** (omitted governing context could previously pass this layer; it no longer can, and detached context cannot borrow citations). Retain only as a **meaning-layer note** for the separate conditional/exception checks — not a defect of this change and not requiring this helper to grow semantics. No mandatory fix proposed; none is directly causal.

## Evidence limitations

- Third allowed item (parenthetical regression test) not read — budget; `_check_conditional_branch_mapping` (2171) not read — budget; `_iter_expression_atoms` body not read (per-candidate claim rests on its call context at `4926-4930`).
- No tests executed; acceptance/rejection examples are code-read inferences. The owner-reported 1611-pass run and replay behavior are owner-reported, unverified here. Synthetic presence tests, when cited from the prior pass, prove presence only — not clinical equivalence or authorization.
