# Codex Execution Review: phase5-slice61am-p804-source-closure-current-route-verification-20260828

## Verdict

**Accept with Codex remediation.** The generic source-closure repair contract
and its current-route verification packet are accepted for independent
conference review. This is not clinical acceptance of the D001 p804 content,
does not publish a control point, and does not authorize a model replay by
itself.

## Worker Outputs

- `worker_01` traced the full gate -> repair mapping -> runner authorization ->
  bounded restore/validate path and confirmed that the implementation contains
  no D001/p804-specific rule. It also found two shared edge cases that the
  earlier focused suite had missed: a mixed publication report could combine a
  source-closure authorization with atom-level spans, and a control-scope
  closure issue could lack the candidate id needed to seed the closure.
- `worker_02` reran **42 focused** and **1002 protocol-layer** tests, then
  exercised merge, split, source loss, cross-source absorption, shuffled/frozen
  candidates, empty closure, and transitive closure through the real runner
  loop. It distinguished runner coverage from direct restore-function coverage
  instead of treating the test count as proof.
- `worker_03` independently verified the immutable v8 artifact hashes and
  replayed real A4/A5 wire restoration. The p805 out-of-scope edit is restored
  to A4, while p804 still contains the unconditional sibling and still triggers
  `CONDITIONAL_EXEMPTION_SCOPE_SPLIT`.
- All workers ran on the packet-declared `codebuddy-cli/glm-5.3` route with no
  fallback. No worker modified clinical artifacts, ran a semantic model, or
  published a control point.

## Manager Assessment

The route declared no execution manager; Codex owns integration under the
Hermes governed workflow. Worker acceptance required remediation rather than a
simple majority judgment:

1. `publication_repair_error` now normalizes candidate repartition and source
   closure rewrites so they never carry atom-level spans from another issue in
   the same report. `combined_repair_error` enforces the same invariant across
   independently constructed errors. Fine-grained issues are re-evaluated on a
   later validation pass instead of creating an impossible mixed scope that
   consumes the repair budget.
2. A control-scope `CONDITIONAL_EXEMPTION_SCOPE_SPLIT` issue with no direct
   candidate id now resolves its closure seed through the existing
   control-to-candidate map. This does not widen the authorized source union.
3. The existing runner integration test now includes a second atom-level issue,
   proving that the mixed report reaches source-closure repair instead of an
   inevitable `REPAIR_SCOPE_ESCAPE` loop. Separate tests cover mapping-level
   aggregation and control-scope candidate resolution.

Worker_02 recommended converting every exploratory runner probe into a formal
runner test. Codex did not duplicate all existing restore-level tests: the
contract already has adversarial unit coverage, while the highest-risk mixed
scope now has a real runner regression. This is the smallest coherent test
surface for the observed defects.

## Codex Independent Verification

- Focused contract suite after remediation: **45 passed**.
- Full `tests/v2/protocols` suite after remediation: **1005 passed, 58
  warnings** in 146.64 seconds.
- `compileall` and `git diff --check`: passed.
- Current hashes:
  - `protocol_control_repair_errors.py`:
    `c5453a8d6536adb930714487c8b6d8f8751f51e4b8954356df862dd154c9039a`
  - `protocol_control_deconstructor.py`:
    `3f5e6d005c37b8ba13756ed0e7c05e34713a822ec5eeb8c236b227d259d6477d`
  - focused contract tests:
    `ee41328aa0cb44d30513075b90588f0017ddb46c093ee758831f39d882e07c48`
- Real v8 remains immutable and rejected. The engineering contract can freeze
  p805 correctly, but the old A5 response did not perform the required p804
  closure-level semantic rewrite.
- The execution auditor incorrectly compared historical packets against the
  route manifest at audit time. Codex changed it to read the immutable worker
  route from each packet's execution context. Both the earlier
  `cursor-cli/auto` packet and this `codebuddy-cli/glm-5.3` packet now pass
  route-identity audit against their own creation records; current manifests
  remain authoritative only for creating new packets.

The next admissible step is an independent conference on the final repaired
contract and the evidence boundary. A new semantic replay remains prohibited
until Codex reviews that conference.

## Cleanup Decision

The review gate and execution audit must pass before cleanup. Then archive only
runner-owned prompts, reports, and logs through `cleanup-execution`; retain
reviews, metrics, code/tests, Trellis checkpoints, and immutable v8 evidence.
