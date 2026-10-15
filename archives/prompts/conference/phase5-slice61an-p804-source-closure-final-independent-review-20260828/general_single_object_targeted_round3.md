This is targeted continuation round 3 in the same session. Do not restart the task,
open a new session, modify files, run a model replay, or publish controls.

Codex accepted your F1 and C3 findings and changed the current worktree after your
round-1 review. Your round-2 report repeated the pre-remediation F1 state and is not
an acceptance review of the current code. Re-read the current files rather than
relying on prior line-number assumptions:

- `app/agents/protocol_control_deconstructor.py`, especially current lines 2576-2645.
  The runner now computes the transitive candidate-source closure, compares its full
  source-unit union with the repair issue's own `structure_unit_ids`, and sets
  `repair_scope_unknown` when a source-closure rewrite would exceed that authority.
  Ordinary candidate repartition remains transitive and is intentionally unaffected.
- `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py`, especially
  current tests `test_control_scope_gate_issue_seeds_originating_candidate_closure`,
  `test_scope_split_runner_uses_source_closure_not_atom_repair`, and
  `test_scope_split_runner_rejects_source_closure_beyond_issue_authority`.

Codex independently ran the current worktree after these changes:

- focused contract file: 47 passed;
- full `tests/v2/protocols`: 1007 passed, 58 warnings;
- `compileall` and `git diff --check`: passed;
- current SHA-256: deconstructor
  `55735333bbce470c38068c18b7dab213a9bd4d9988d4b429c21543a15e0b78ff`, repair
  errors `c5453a8d6536adb930714487c8b6d8f8751f51e4b8954356df862dd154c9039a`,
  focused tests `2c13721a6a56ca53f079abb528c13df2a564c36e3c2d883c00999cb6e3c7c2f3`.

Independently inspect the current implementation and answer only these questions:

1. Does the new authority check actually close F1 for source-closure rewrites, including
   a candidate spanning the authorized unit and a must-freeze unit?
2. Does the positive runner test still prove a legal same-unit merge, while the negative
   runner test proves no second model call occurs on authority escape?
3. Does the new control-scope test close C3 from gate issue shape through
   `originating_candidate_id` mapping into the repair seed?
4. Did the repair weaken ordinary candidate repartition or source/atom conservation?
5. Are there any remaining correctness blockers in this bounded source-closure contract?

Keep deferred production wiring, committed replay harness, repair-budget policy, and a
new immutable D001 model replay explicitly outside this bounded acceptance. They remain
future prerequisites and must not be mistaken for completed work. Likewise, engineering
acceptance does not mean v8 p804 clinically passed; v8 remains immutable, rejected, and
unpublished.

Return a concise complete updated Markdown report with: Boundary Check, Current-Code
Verification, Remaining Blockers, and Recommended Disposition. Separate observed code,
Codex-reported test evidence, inference, and recommendation.
