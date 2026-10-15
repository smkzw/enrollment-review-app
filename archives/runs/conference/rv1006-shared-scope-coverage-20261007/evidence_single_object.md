我按只读边界审这处共享访视范围覆盖改动：先读会议上下文、计划和指定五处 diff，再核对完整定义与测试，不改文件、不跑测试。The shared-scope coverage predicate does what this change asks on the literal ledger. A saved source-review consumer still requires the opposite literal status, so this is not product acceptance, adoption, or signoff.

## Findings

### 1. Medium, fail-closed: literal `expressed` conflicts with saved source review

`source_statement_coverage` now returns `expressed` for the shared-scope relative candidate. `_validate_saved_source_review` still requires the recomputed literal status of every `additional_requirement` to be `candidate_linked`, and the stored row to be `semantically_aligned`.

```2769:2772:app/services/protocol_control_execution.py
            if (entry.status != "semantically_aligned"
                    or expected.status != "candidate_linked"
                    or entry.action_candidate_indexes != expected.action_candidate_indexes
                    or entry.candidate_indexes != mapped.candidate_indexes):
```

`expected` is a fresh `source_statement_coverage` result after index remap only (`hydrated_source_coverage_indexes`, deconstructor 4587–4603). That function does not change `status`. The new test requires the fresh status to be `expressed`:

```10923:10923:tests/v2/protocols/test_slice58c_control_deconstructor.py
    assert source_statement_coverage(batch, inventory, _wire(candidate=candidate))[0].status == "expressed"
```

`can_compile_relative_stage_requirement` only runs when `review.decision == "additional_requirement"` (stage compiler 296–297). For that decision, both stored shapes fail this check: stored `expressed` fails the `semantically_aligned` arm; stored `semantically_aligned` fails because the recompute is `expressed`, not `candidate_linked`.

Decisive counterexample, no clinical text: the relative fixture at test 10878–10923, then `_validate_saved_source_review` while that statement remains an `additional_requirement` with a `fully_expressed` alignment item. The validator raises `SourceCandidateAlignmentValidationError` (`已核候选与来源覆盖账不一致`). This blocks resume consistency. It does not publish the candidate. The new test never calls this validator. `test_two_sourced_actions_insert_together_without_rewriting_existing_draft` clears `source_target_review.items` after a successful run (11027), so that success path does not enter the `additions` loop.

### 2. Low: coverage credits a time word that is only a substring of the exact scope

`_candidate_preserves_source_time_words` appends the whole normalized `scope_quote`, then uses substring `word in text` (deconstructor 4629–4639). Assembly is stricter: `can_compile_relative_stage_requirement` requires each `_time_parts` piece to be an exact scope part or a substring of the action sentence (stage compiler 319–321). A non-compiler wire can therefore be literal-`expressed` when a fragment such as `D-1` sits inside the verified scope excerpt `筛选/导入期（D-7~D-1）：` and the action sentence is exact. That fragment is inside the verified scope string. It is not a whole-paragraph or wrong-span proof. The compiler path still rejects `给药前90分钟` (test 10943–10947).

### 3. Low: coverage span check is membership, not span text

The new arm accepts a pair when the span id is in the owned unit’s span set and the excerpt equals `scope_quote` (deconstructor 4634–4635). It does not re-read that span’s text. `_validate_exact_atom_sources` does, and raises `FABRICATED_EXCERPT` when the excerpt is not a contiguous string of that span (deconstructor 3263–3276). The negative test goes through `_wire` (test 10930–10935). A direct `source_statement_coverage` call on an already built wire can still treat an owned but wrong span as the scope pair.

## Good paths

Coverage (`source-statement-coverage/v5`), deconstructor 4606–4639. With at least two time words, the scope enters the literal account only when all of these hold:

- `scope_quote` is outside the action sentence (`scope not in quote`).
- The atom statement equals that sentence after trailing `。；;.!！?？` are removed.
- Some zip pair has an owned span and an excerpt exactly equal to the normalized scope, colon included. `normalize_source_excerpt` only does NFKC, quote folding, and whitespace removal (source interpretation 1907–1910).

The action’s own relative phrase still has to appear in the rendered statement or continuation. `完成导入治疗后` is not in the scope string, so the scope citation cannot replace it.

These constructions stay off the expressed ledger:

- Whole-paragraph citation: `source_excerpts[0]` replaced by the full unit excerpt fails `excerpt == scope`. Status stays `candidate_linked` (test 10925–10929). The obligation-role rule still requires the atom statement to equal the statement quote (deconstructor 4414–4419). The diff does not change `test_source_coverage_does_not_treat_whole_sentence_citation_as_whole_action`; a grep hit still asserts `candidate_linked` at test line 2635. That fixture body was not read.
- Wrong position: span `unowned-span` fails `_wire` until it is also added to the candidate span list, then coverage stays `candidate_linked` because the span is not in the unit span set (test 10930–10935).
- One time word still returns true immediately (deconstructor 4616–4617). That early return is unchanged. The parametrized `None` case has only `完成导入治疗后`, which is inside the action sentence.

Assembly (`control-relative-stage-requirement/v9`), stage compiler 291–322 and 675–705. Before the wire is built, compile requires a frozen prior stage strictly before the selected stage, `review.target_id` equal to `target_procedure_id`, and the procedure’s execution stage equal to the selected stage. Scope parts may live only in the shared scope; every other declared time part must sit in `relative_time_excerpt`. That relative excerpt must equal `review.source_time_excerpt`, occur in the action sentence, and occur in `obligation_statement`. `time_constraint` stays `None` (test 10919). Reversed stage raises `先后` (10937–10939). Scope `治疗期` raises `StageBoundCompilationGap` (10940–10942). `exception_words`, `unresolved`, and `requires_temporal_resolution` still refuse the path (632–634, 299–300). The supplementary relation is still one `supplementary_requirement` with the same notes (706–713). `exception_expression` stays `None`.

Inline pairing from the compiler: an empty ancestor citation puts `[stage_scope_excerpt, quoted_text]` on the same owned span; a returned citation keeps only the action excerpt on the atom and parks the scope on the node (742–751). The tested excerpt is a colon-prefix of the same owned unit, and the test expects `expressed`, which matches the inline arm.

Versions move together for the changed contracts: relative constant, `Literal`, and schema name `protocol_control_relative_stage_requirement_v9` (stage compiler 51, diff at the response-format name); transport expectation v9; deep identity list carries that constant plus `source-statement-coverage/v5` (execution 1895–1898). Stage-bound stays v10 and shared prohibition stays v3. The five-path diff does not write new digests over stored hashes. `_same_deep_components_with_current_gate` (1936–1950) does not exempt `compiler_versions`, so an old v8/v4 identity fails closed instead of being rewritten.

Adoption and signoff stay separate files, both outside the diff. `restricted_batch_from_review` still returns no batch unless the run is `需要核对`, the last attempt is `publication_invalid`, and the error class is one of the three named classes (restricted source 320–328). Coexisting executable siblings still need `expressed` plus a self-contained standalone proof (243–245, 416–418). The module comment says a shared qualifier outside the action cannot use that narrow path (217–222). `candidate_linked` fails those `expressed` checks. Publication remains `validate_protocol_control_publication` at gate version v44 (gate 65, 5255). This review did not re-walk the publication checks.

## Dangerous paths checked

| Path | Result |
|---|---|
| Shared heading cited exactly, action keeps `完成导入治疗后` | Literal `expressed` |
| Whole unit excerpt used as the scope slot | `candidate_linked` |
| Scope text paired with a span outside the unit | `candidate_linked` after `_wire` |
| Prior and selected stage reversed or tied | Compile gap `先后` |
| Scope label `治疗期` | Compile gap |
| Extra time `给药前90分钟` | `can_compile` false and compile gap |
| Sibling ref sharing | New arm does not add a scope ref; demotion at 4573–4583 still uses the quote inside the atom statement |
| `D-7~D-1` inside the scope | Admitted as scope text only. `time_constraint` stays empty. The duration regex `(?:W\|D)\d+` does not match `D-7` (source interpretation 1934) |

## Minimal fix

In `_validate_saved_source_review`, treat a recomputed `expressed` ledger as consistent with a stored `expressed` row or with the existing `semantically_aligned` overlay. Keep recomputed `candidate_linked` consistent only with stored `semantically_aligned`. Do not accept stored `candidate_linked` as expressed, and do not change the publication gate, `restricted_batch_from_review`, or approved R1 behavior.

## Limitations and unread evidence

Static reading only. Tests were not run. Twenty-one material calls were used: nineteen inside the file list, then two gap calls. The ancestor function body was not read. `resolve_ancestor_scope_citation` is at `app/protocols/control_scope_sources.py:26`; only its call site was read. If that function returns a citation for this colon-prefix, the compiler omits the scope excerpt and the new positive assert fails closed.

Also unread: `_candidate_source_texts`; the whole-sentence test fixture; `source_statement_context_is_self_contained` and `source_statement_is_standalone_action`; publication check bodies; execution around line 3777; runner save order; `tests/v2/services/test_protocol_control_execution.py` beyond grep hits. Context and plan files are still TODO shells. The earlier 1026 pass was before this coverage diff and is not evidence for it. No clinical source, raw answer, or rerun was used.

## Recommendation

Conditional, and not acceptance. Coverage and v9 assembly match the asked literal rule for an inline shared scope plus the action’s own relative phrase. Whole-paragraph and unowned-span citations stay `candidate_linked`. Publication, restricted adoption, and semantic alignment were not widened in code. Reconcile the saved-review status pair before calling the product path closed.
