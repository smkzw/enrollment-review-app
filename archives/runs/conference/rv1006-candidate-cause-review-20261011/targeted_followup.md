我按已接受的边界只核对这次修复：终态范围、政策失败、整段异常立即返回，以及服务层是否仍把新鲜否定当成已耗尽证明。差异显示整段异常多了一处返回。我先核对它的缩进是否真的盖住「已有响应」的绑定失败，再看政策失败和混合时间下标。# Conference Output: rv1006-candidate-cause-review-20261011 - evidence_single_object

## Output

未做最终验收，也没有运行测试或临床核对。下面只是当前差异的静态核对。语义分支的精确相等、整段异常立即返回、以及新鲜否定不能变成已耗尽证明，这三处与本次接受条件一致。仍有一处实质残留：政策失败会在比较时间下标之前返回。

### 证据

`protocol_control_deconstructor.py` 10442–10463 行：`alignment_response is None` 时仍先改成传输、身份或预算码，再返回。10464–10469 行：只要进入该 `except`，无论响应是否存在，都立即返回刚才那条失败。保留的负向对齐不会再走到 10509 行之后。

10511–10527 行：任意 `alignment_failures` 中 `code == "EVIDENCE_POLICY_UNJUSTIFIED"` 即用 `policy_failures[0]` 再追加一条并返回。这里没有把失败下标与 `temporal_unresolved_indexes` 做相等比较。

10528–10569 行：只有 `failed_indexes` 与仍未决的时间下标集合相等，且 `rejected_temporal` 全部是 `SOURCE_CANDIDATE_ALIGNMENT_INVALID` 时，才写 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 并返回。否则 10570–10581 行仍对全部时间下标抛 `SourceTemporalScopeUnresolved`。`uncertain` 不是 `incomplete`，不进入 `failed_indexes`。这些返回都不写 `final_output`。

`protocol_control_execution.py` 的差异仍只有 2157 行的 `candidate-time-failure-cause/v1`。两个续跑码和上限 2 不在本次差异里。服务源码中没有 `SOURCE_CANDIDATE_ALIGNMENT_INVALID` 这个续跑码。

`test_protocol_control_execution.py` 7817–7821、7880–7884 行：`fresh_negative` 断言修复单元仍是 `[]`，并且 `_preserved_negative_alignment_proof` 返回 `None`。7852–7853 行把 `restricted_batch_from_review` 换成了 `None`。无读者断言只在 Runner 测试的 `reply_kind == "negative"` 分支。

### 推论

精确相等不成立时，无效兄弟会连同剩余时间项一起留在原时间失败里，不会单独获得续跑。这与「有剩余不确定时间项就保留原时间失败」一致。响应体解析或绑定异常的终态不再被保留的负向结果替换。身份、传输和预算仍走无响应分支。

政策分支没有同一条相等约束。一个不覆盖全部时间下标的政策失败，甚至一个非时间项上的政策失败，都会直接返回。剩余时间下标到不了 10570 行。终态码确实不是语义票，但剩余时间失败没有保留。10514 行只用 `policy_failures[0]`，后面的政策陈述不会进入最后一条 `error_detail`。

`fresh_negative` 证明的是已耗尽否定证明不成立，不是生产路径不会形成受限来源。受限函数在这个测试里被替换了。静态上，时间证明仍要求终态类恰好是 `TEMPORAL_SCOPE_UNRESOLVED`；这次语义终态对不上。

### 建议

改 10511–10527 行。有政策失败时，不要进入 10536 行的语义返回。仅当全部政策失败的 `statement_ids` 并集正好等于 `temporal_unresolved_indexes` 时，才以 `EVIDENCE_POLICY_UNJUSTIFIED` 返回，并把该并集写入终态 `statement_ids`。只要还有时间下标落在这个并集之外，就不要返回，让 10570 行对原时间范围抛时间失败；已写入的政策尝试留在前面，不能改记成语义未核。

服务测试若要覆盖生产消费者，应对这个新鲜否定形状调用真实的 `restricted_batch_from_review`，而不是把它替换成 `None`。在那之前，不要把 7884 行当成「生产不会采用」的证据。

### 不确定性

没有执行混合、政策、坏 JSON 或服务检查点测试，因此不能确认夹具运行后的终态与上述静态分支一致。`uncertain` 能否通过 `validate_candidate_alignment` 并保持为非失败项，只根据校验条件推断，未实际构造该夹具。
