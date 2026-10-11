This is targeted continuation round 4 in the same session. Remain read-only. Do
not restart, modify files, run a model replay, or publish controls.

Your round-3 current-code review accepted the authority guard but found two residual
scope issues. Codex repaired both in the current worktree. Re-read current code and
tests; do not rely on earlier report text.

1. `tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py` now makes
   `test_scope_split_runner_rejects_source_closure_beyond_issue_authority` use a
   literal spanning candidate with source units `su-01` and `su-02`, while the issue
   authorizes only `su-02`. It still proves one attempt and no continuation call.
2. `app/protocols/protocol_control_repair_errors.py` now gives one structural repair
   class exclusive ownership of each repair round. Source-closure issues take
   precedence, candidate-repartition issues are next, and ordinary atom/clinical
   issues remain in the explanatory message but cannot add candidate ids, structure
   units, spans, or mutable dispositions to that round. `combined_repair_error` uses
   the same rule. This closes your round-3 residual observation that an atom issue on
   another unit could widen `mutable_structure_unit_ids`.
3. The focused mixed-publication and mixed-combined tests now use an unrelated issue
   on `su-01` / `pcc-other` and assert that only `su-02` / the closure candidates
   remain in the repair scope.

Codex reran the current state after these changes:
- focused contract file: 47 passed;
- full `tests/v2/protocols`: 1007 passed, 58 warnings;
- compileall and `git diff --check`: passed;
- SHA-256: deconstructor
  `55735333bbce470c38068c18b7dab213a9bd4d9988d4b429c21543a15e0b78ff`,
  repair errors `69f0d6c2dddb156681d21119820d075518a61c6dfd3ee0ffd84831bc3cfcbb47`,
  focused tests `f36817fdbf18fc306e66d68a11af67b2f6bcff779026845b3c2cc23b3104649b`.

Independently verify:
- the exact spanning-candidate F1 case now fails closed before a second model call;
- mixed issues cannot widen candidate, source-unit, span, or disposition authority;
- error messages still preserve all findings so deferred issues reappear on the next
  validation round;
- ordinary candidate repartition remains transitive within its own authorized repair
  issue and source/atom conservation is unchanged;
- no remaining correctness blocker exists in this bounded contract.

Keep replay harness, repair-budget policy, production wiring, and a new immutable D001
replay outside this acceptance. v8 remains rejected and unpublished.

Return a concise complete Markdown report with Boundary Check, Current-Code Verification,
Remaining Blockers, and Recommended Disposition. Separate observed code, Codex-reported
test evidence, inference, and recommendation.
