# Codex Execution Review: phase5-slice61al-p804-source-closure-repair-20260828

## Verdict

**Accept with Codex remediation.** The bounded implementation is accepted as a
generic repair contract. This verdict does not accept the D001 p804 clinical
output, does not publish any control point, and does not authorize a model
replay by itself.

## Worker Outputs

- `worker_01` reconstructed the real v8 A4/A5 failure path and showed why a
  single-candidate repair cannot remove a split conditional exemption when the
  offending sibling remains frozen. It proposed source-union conservation and
  out-of-closure freezing as the governing invariants.
- `worker_02` separated `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` from ordinary
  candidate repartition and implemented `allow_source_closure_rewrite` so all
  candidates from the authorized source closure may be merged, split, or
  rewritten while other sources are restored from the previous wire.
- `worker_03` added adversarial coverage for merge/split, source absorption,
  source loss, empty closure, shuffled candidates, multiple frozen siblings,
  generic Chinese guidance, and an incomplete rewrite that must remain
  rejected.
- All workers stayed within the declared code/test boundary. No semantic model
  ran and no clinical artifact or published control point was changed.

## Manager Assessment

The live route declared `no_manager=true`; Codex therefore owns integration and
acceptance under the Hermes governed workflow. Worker output was not sufficient
by itself: the initial change
propagated `obligation_source_span_ids` into a source-closure rewrite. The real
runner would then request atom-level repair and closure-level rewrite at the
same time, causing `_restore_bounded_wire_repair` to reject every attempt before
the new contract could operate.

Codex repaired the shared mapping in
`app/protocols/protocol_control_repair_errors.py`: expression repair retains
atom spans, while candidate-expression and source-closure rewrites do not
propagate atom-level obligation spans. A runner integration regression test now
proves that scope-split repair reaches the source-closure path instead of the
atom-repair path.

## Codex Independent Verification

- Focused contract suite: **42 passed**.
- Full `tests/v2/protocols` suite: **1002 passed, 58 warnings**.
- `compileall` and `git diff --check`: passed.
- Real v8 A4/A5 offline restore with the accepted contract:
  - p805 is restored exactly to A4 and the A5 out-of-scope p805 edit is dropped;
  - p804 remains two candidates, including an unconditional sibling;
  - therefore the existing v8 content is still clinically rejected and is not
    made acceptable by the engineering repair alone.
- The workflow guard changed unexpectedly during the pass and temporarily
  failed at import due to a self-reference inside `ROUTES`, then failed because
  `route()` read an undeclared `--at` argument. Codex made the minimal tool-only
  repairs and verified `py_compile`, live `route`, and `audit-execution --help`.

The next admissible action is independent conference review of the repaired
contract. Only after that review may Codex decide whether one new immutable
model replay is justified. The rejected v8 run remains immutable.

## Cleanup Decision

Run the governed execution audit first. If it passes, remove only runner-owned
temporary prompt/process material through `cleanup-execution`; retain worker
reports, review, metrics, tests, checkpoints, and the immutable v8 evidence.
