Delegated mode. Continue the same bounded worker session for task `phase5-slice58p-mixed-paragraph-atomization-20260826`, role `worker_01`.

The real D001 rebuild rejected the first implementation. Modify only `app/protocols/full_protocol_coverage.py`; do not touch tests, artifacts, task records, source protocols, subjects, browser work, or runner-owned reports.

Observed root cause:

- soft punctuation splitting truncated complete clinical arrangements;
- `1:1:1` and `2:2:1` were split at `:`;
- dose combinations were split at commas;
- an II-phase reference nested inside a III-phase dose sentence was treated as a new phase arrangement;
- `body.p729`, `body.p801`, `body.p815`, and `body.p1237` produced 17 clinically incomplete fragments.

Required correction:

1. Remove soft-punctuation and marker-interval atomization. Do not infer a complete clinical obligation from a phase token.
2. Split only at source-preserving strong sentence/clause boundaries (`。！？!?；;` and newline). Never split inside one strong clause, including ratios, dose lists, parenthetical references, or visit lists.
3. Classify each complete strong clause with the existing phase detector. Coalesce adjacent clauses with the same scope so neutral prose is not exploded into many units.
4. Atomize a graph-level `MIXED` paragraph only when at least two complete strong clauses remain and their phase-scope signatures differ. A single mixed strong clause stays one `MIXED` source unit.
5. Preserve exact ordered source replay, parent `member_source_refs`, parent span ids, deterministic identities, and unchanged IDs for non-atomized paragraphs. Prefer source start/end in derived identity over a fragile ordinal-only identity if this can be done without broad contract changes.
6. Keep residual or composite clauses `UNKNOWN`/`MIXED`; never upgrade them to shared or selected phase merely because another clause was separable.

Expected real behavior:

- `body.p729`: common randomization preamble may separate from the final mixed II/III randomization sentence, but ratios/doses remain intact.
- `body.p801`: the one mixed HbA1c sentence remains intact.
- `body.p815`: the mixed visit-schedule sentence remains intact; later complete pregnancy screen-failure and optional-testing sentences can be a separate neutral atom rather than being lost with it.
- `body.p1237`: complete sentences may separate; the sentence combining II evidence and III continuation/dose recommendation remains intact.

Run the focused 58p test file and adjacent full-protocol tests. Existing tests that require splitting one strong sentence into three phase atoms are now invalid and may fail; report that precisely, do not edit them. Return the complete execution report; do not claim final acceptance.
