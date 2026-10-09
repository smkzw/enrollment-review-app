Trellis SessionStart context loaded.

Starting the read-only review. First, locating the delta surface (no task will be created — this pass is constrained to reads only).

Bash is unavailable in this session (read-only review), so I'll work with Read/Grep only, within the 10-read budget.

Bash is fully blocked in this session, so I'll rely on Read/Grep only and stay within the 10-read budget. Starting with the compiler and its assembly consumer.

Compiler read complete. Now locating the new `RELATIVE_STAGE_SOURCE_DIMENSION_VERSION` consumers and the identity change in the execution service.

Identity diff located: the new token sits in `validator_version`, not `compiler_versions` (execution.py:2079). Now checking the reuse/revalidation path and the review-item contract.

Now the synthetic test families. Reading the relative-stage family first.

Last budgeted read: the ordinary-path negative test that guards the unchanged stage path.

# Read-only engineering review — relative-stage split-field delta

**Reviewed at:** worktree `phase5-clinical-facts-profile`, base `b355ab9…`, current working tree. Route as stated; no writes, no test execution, no model calls, no recursion, no clinical/db/env reads. Budget used: 10 file reads (compiler, execution service ×4, fixed_flow, 2 synthetic test regions, 1 services test); everything else via search only.

**Verdict: no must-fix engineering findings in the inspected delta.** The stated property — a split is accepted only when time equals the reviewed time and the two fields concatenate back to the reviewed action, gated to `RelativeStageRequirement` — is implemented as described and is structurally tight. Two boundary items and the diff-related uncertainties are listed below.

## What was inspected

- `app/agents/protocol_control_stage_compiler.py` complete: `RelativeStageRequirement:90`, preflight `301-352`, prompt/schema `434-509`, compile `645-858`, dispatch `861-882`, assembly consumer `885-912`.
- `app/services/protocol_control_execution.py`: identity + gate `2004-2111`, adoption `3532-3603`, reuse decision/marker `4086-4109`, failed-batch recovery `2648-2775`.
- `app/agents/protocol_control_fixed_flow.py:360-460` (author loop / incremental assembly).
- Tests: `tests/v2/protocols/test_slice58c_control_deconstructor.py:12294-12405, 12760-13332`; `tests/v2/services/test_protocol_control_execution.py:6180-6260`.

## Challenge results

**Escape hatch (stage_compiler.py:696-704).** Condition: `isinstance(selection, RelativeStageRequirement)` ∧ normalized `relative_time_excerpt` == normalized reviewed `source_time_excerpt` ∧ `normalize(rel + action_excerpt) == normalize(review.source_action_excerpt)`. This is an exact partition of the reviewed action with the time piece pinned to the reviewed time. Order is string-enforced (the reviewed action must literally start with the time fragment); omission, insertion, or reversal inside the reviewed action cannot satisfy concatenation equality. Each piece independently grounds: action ⊆ frozen unit excerpt and ⊆ `quoted_text` (`:686-691`), rel ⊆ `quoted_text` (`:739`), full source sentence ⊆ obligation (`:705-708`), rel ⊆ obligation (`:741`).

- **Omitted action restrictions — no finding.** Any restriction inside the reviewed action must appear in one of the two fields (concat equality). `exception_words` / `unresolved` / temporal-resolution still hard-fail (`:664-667`). Restrictions outside the reviewed action were equally outside the old path's guarantee.
- **Wrong or invented time — no finding.** rel must equal the reviewed time (`:699`, `:738`) and be inside the quoted sentence (`:739`); every declared `time_words` fragment must be covered by scope or rel (`:740`). Tests cover invented time (`slice:12968-12972`) and time-fragment grounding (`slice:12957-12960`).
- **Reversed stage order — no finding.** Strict `ReviewStage` index ordering in preflight (`:332-339`) and compile (`:721-730`); test `slice:12962-12964`.
- **Stale target proof — no finding.** Procedure, target id, execution stage, and `target_action ⊆ procedure.source_excerpts` are re-derived from the *current* batch on every compile (`:719-745`); mutation test `slice:12940-12944`. Identity gate (`source_sha256` etc.) prevents cross-source adoption (`execution:3567-3580`).
- **Ordinary stage path unchanged — supported.** Escape is short-circuit-gated on `isinstance(RelativeStageRequirement)`; ordinary selections still require `reviewed_action ⊆ action` (`:703`) plus the original scope/time checks (`:755-758`). Tests: `slice:12311-12313`, `12343-12353`, `12921-12927`.
- **Unchanged siblings / whole-batch — no finding.** Assembly requires equal review/response counts and per-review `expressed` coverage (`stage_compiler.py:896, 909-911`); fixed_flow freezes accepted authors incrementally and only full-validates the last/no-retained iteration (`fixed_flow.py:429-436`). `broken_first`/`joint_failure` tests assert the accepted sibling survives, the failed item is not persisted, and the original draft is not rewritten (`slice:13083-13101`).
- **Wrong meaning / recovery — no finding.** Split positives in two source layouts (`筛选/导入期（D-7~D-1）：完成导入治疗后再次核查资格。` and `导入治疗结束后再次核查资格。`), negative mutations (dropped “再次”, truncated time, truncated obligation), and partial-resume without re-reading completed authors (`slice:13184-13287`). The obligation must contain the whole sentence (`:705-708`, test `:12915-12920`), so the atom proposition cannot be the split fragment.

**Historical identity reuse — mechanism verified, with a boundary note.** The new `RELATIVE_STAGE_SOURCE_DIMENSION_VERSION` sits in `validator_version` (`execution:2079`), while `STAGE_BOUND_REQUIREMENT_VERSION`/`RELATIVE_STAGE_REQUIREMENT_VERSION` remain in `compiler_versions` (`:2027-2028`). The gate permits reuse only when all fields except `validator_version` match (`:2097-2111`); the gate-only test shows no model calls and `revalidated_from_gate_version` recorded (`services test:6200-6260`). Adoption revalidates the saved review and saved output under current validators (`:3597-3602`) and, for previously failed batches, recovery re-derives under current validators (`:2716-2765`); reuse as a success requires step state `completed` (`:3560`), so previously failed split-field runs cannot be waved through from cache.

## Boundary notes (not must-fix)

1. **"Revalidated" ≠ re-running the changed function.** `compile_stage_bound_requirement` is invoked during authoring/assembly, not during adoption revalidation (`_validate_saved_source_review` + `_validate_deep_batch_output`, `execution:3597-3602`). For *this* delta the acceptance set only widens, so an old success remains valid under the new compiler and adoption is materially equivalent. If this same function is ever made *stricter*, marking it as validator identity rather than bumping `compiler_versions` would let saved successes bypass the stricter check. The placement chosen here is correct for a permissive change; it is not a general precedent.
2. **Normalized, not byte, equality.** The escape relies on `normalize_source_excerpt`; punctuation/whitespace variants are equal by design. Consistent with pipeline conventions; behavior surfaced only by reading, not execution.

## Checks not performed / residual uncertainty

- No tests executed and no runtime repro (per constraints); all statements above are source-reading evidence, not pass/fail results.
- `git diff` against `b355ab9` was unavailable in this session (Bash denied), so "prompt, schema, versions unchanged; only validator identity added" is verified for current-state consistency (new token only in `validator_version`; schema names `…stage_bound_requirement_v10` / `…relative_stage_requirement_v9`; candidate constructor shared by both branches) — not against the base revision.
- Upstream review-item validators (`SOURCE_ACTION_MISMATCH` :1847-1862, `SOURCE_TIME_INCOMPLETE/UNGROUNDED` :2054-2093) and `_validate_saved_source_review`/`_validate_deep_batch_output` bodies were seen by grep/context only; the escape rests on the premise that the reviewed action is a contiguous verbatim span and the reviewed time is independently checked. That premise is the residual trust boundary.
- Deconstructor call sites `7751/9119/9152` and `_saved_deep_run_result` were not read; whether a FLOW-variant saved success stores the compiled wire (and is therefore adopted without recompiling) is inferred, not proven.
- The gate-only test tampers `validator_version` to one placeholder string; it proves the reuse mechanism, not compatibility with a real pre-delta identity.

No project/drug-specific fixes, frameworks, or extra full-model rereads proposed. This is engineering review only — not clinical approval, independent-model gold, publication, or product acceptance. No Trellis task was created and no file was written or modified.
