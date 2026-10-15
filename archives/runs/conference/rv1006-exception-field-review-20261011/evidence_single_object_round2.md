上一轮的短片段和整句异议要按现在的消费者路径重核。我只读这四个文件的当前 diff，以及补上的定义和合成用例。上一轮把「子串或整句不能当完整例外」说重了。按现在的覆盖账，例外功能陈述不会因为候选抄了动作就被标成已表达；整句例外可以保留。空白疑问、传输重试和失败码分类已经补上。静态阅读没有看到剩余的控制漏洞。

# Conference Output: rv1006-exception-field-review-20261011 - evidence_single_object

## Output

撤回上一轮的主异议。短片段或整句 `exception_words` 不是完整含义证明；当前消费者也不把它当成证明。`source_statement_coverage` 不再把带 `exception` 的陈述标成 `expressed`。它停在 `candidate_linked`，随后仍要走现有的目标核对、候选语义核对，以及绑定当前陈述哈希的证明，才能进入最终消费。合法例外可以是整句摘录。标点不能充当语义标准。

针对上一轮其余意见的修复，静态上成立：空白 `unresolved` 被拒绝；传输失败只在累计来源额度内再读，坏内容不能再读；两个失败码已进入现有服务分类，只有传输码可重试；未调用没有伪造模型原文；失败返回保留旧核对、覆盖账和对齐，且不作为采用结果。测试没有执行。这不是临床或最终验收。

没有剩余的实质性控制漏洞。有一处非阻断的诊断文案：两个新失败码没有单独说明，详情仍落到通用句。

## Evidence

- 当前差异仍只在那四个文件：`protocol_control_source_function.py`、`protocol_control_deconstructor.py`、`protocol_control_execution.py`、`test_slice58c_control_deconstructor.py`。相对 `53cdd1bb` 约 344 行新增。没有跑测试。
- `source_statement_coverage` 在 `app/agents/protocol_control_deconstructor.py` 约 4747–4749 行：只有 `expressed`、非原生访视范围、没有 `unresolved`，且 `decision_functions` 不含 `exception` 时，才把候选放入 `linked_candidates`。约 4778–4784 行：没有 `linked_candidates` 时，有单元候选则为 `candidate_linked`，不会变成 `expressed`。
- `target_review_indexes` 在 `app/agents/protocol_control_source_interpretation.py` 约 1804–1805 行：`status != "expressed"` 的入排处置仍要逐项核对。约 9098–9101 行在候选草稿之后按当前来源重算覆盖账，不用失败返回里保存的旧账决定是否跳过核对。
- 对齐证明通过后，约 10368–10377 行才把该条改成 `semantically_aligned`。`_alignment_input_identity` 使用整条陈述的 `model_dump`。`_source_statement_reuse_identity` 约 7384–7400 行包含 `exception_words` 和 `unresolved`。
- `validate_candidate_alignment` 仍只做字面约束：没有 `exception_words`，或候选另有 `exception_expression`，不能 `fully_expressed`；有摘录时，摘录须出现在所选原子文本中。它不判断摘录是不是完整例外从句。
- 新用例仍允许整句进入 `apply_source_function_field_repair` 和 `bind_candidate_alignment`，并断言补正后 `source_statement_coverage(...)[0].status == "candidate_linked"`。同用例加入第二条陈述，断言 `revised.statements[1:]` 不变。空白疑问用 `[" "]`，期望匹配「具体内容」。
- 空白检查在 `apply_source_function_field_repair` 的例外分支：`any(not normalize_source_excerpt(question) for question in revised.unresolved)` 则拒绝。
- 历史门禁约 7895–7896 行：`called is True` 且 `outcome != "transport_failed"` 才进入 `seen_exception_repairs`。调用前计入 `source_repairs`。传输记录因此占用累计额度，但不封锁额度尚余时的下一次读取。坏摘录和坏 JSON 的结局不是 `transport_failed`，恢复时不再调用。
- 合成用例对传输失败使用 `max_schema_repairs=3` 时期望再读一次且 `final_output` 存在、`called` 合计为 2；同一条历史在 `max_schema_repairs=1` 时期望零次再读且没有最终输出。坏内容分支期望零次再读。
- 未调用时 `raw_output_text` 为 `None`，`raw_output_chars` 为 `None`，结局是 `publication_invalid`。`_saved_source_scope_question_history` 约 4323–4326 行和 4339–4342 行允许这种例外记录没有原答。哈希对应的是异常字符串，不是一段模型答复。
- 失败返回约 8528–8534 行带回 `resume_source_target_review`、`resume_source_candidate_alignment` 和 `resume_source_statement_coverage`。此时 `final_output` 仍为空；`_validate_saved_source_review` 只在有最终输出时调用。
- 服务约 4825 行把 `SOURCE_EXCEPTION_FIELD_REPAIR_TRANSPORT_FAILED` 和 `SOURCE_EXCEPTION_FIELD_REPAIR_INVALID` 放入失败码集合。约 4855 行只有传输码进入可重试集合。`SOURCE_EXCEPTION_FIELD_REPAIR_VERSION` 被加入 `_deep_component_identity` 的版本列表。
- 约 4868–4890 行的详情映射没有这两个新码，未命中时使用「深析批次在限定修复次数内未产出合规输出。」

## Inference

- 上一轮的错误在于把写入时的子串检查和 `bind_candidate_alignment` 成功，说成确定性的完整表达。绑定发生在覆盖账之前；覆盖账对例外功能不再给出 `expressed`。基线最终消费看的是重新核对后的 `semantically_aligned` 和当前陈述哈希，不是「候选抄了动作」。
- 整句被接受与这个消费者一致：它可以通过字面绑定，但不能靠覆盖账跳过语义核对。短片段同样不能跳过。含义是否完整仍由当次目标和候选核对决定。
- 传输失败的第一次调用已经把 `called` 记为真，所以额度耗尽后的恢复会在调用前停止，并写成未调用的 `publication_invalid`，失败码是 `SOURCE_EXCEPTION_FIELD_REPAIR_INVALID`，服务不再重试。这符合「只在累计额度内重试」。
- 同一轮里先改到某条的 `exception_words`、后一条又失败时，返回的是改后的来源加改前的核对输入。下一轮开跑时的复用身份按当时来源重算；对齐证明仍要匹配含新字段的陈述哈希。这次差异没有一条同版本路径，能在字段变化后沿用旧的 `fully_expressed` 证明。
- 前置流程的可支持索引要求功能集合落在 `{"action", "time_validity"}` 内。带 `exception` 的陈述进不了那条编译支持集合。因此前置保存校验里「新增要求必须是 `expressed`」这一条，不会被这次覆盖账改动直接走到。

## Recommendation

- 不要恢复标点切句、唯一片段或「不得等于整句」这三条完整性标准。
- 控制路径可以保持现状。若要消除误导，只在服务详情映射为两个新码各写一句：传输失败写明可在原额度内续读；内容无效写明该条补正不再重复。不要改重试分类。
- 回归仍由拥有者执行。至少覆盖：例外陈述在候选抄写全文后仍是 `candidate_linked`；传输失败在额度 3 和额度 1 下的分支；空白 `unresolved`；第二条陈述保持不变。

## Uncertainty

- 测试和运行时都没有执行。上面关于最终输出、服务重试和服务保存的结论是静态推断。
- 没有检查生产传输是否把超时包成 `uncertain_completion`。那种异常会得到 `FLOW_COMPLETION_UNCERTAIN`，而不是新的例外传输码。裸 `TimeoutError` 才会落到新的可重试码。
- 没有用前置流程夹具运行例外陈述。支持条件已从源码读到，但是否另有手工组装的前置结果，未核。

## Objections

- 上一轮把整句参数组当成缺陷，与现在的消费者合同相反。该组只证明字面合并和覆盖账不升为 `expressed`，不证明例外语义已完成。
- 没有新的控制层异议。通用失败详情会把「额度用尽」和「摘录不合格」说成同一句，但不改变码值、重试或是否再次调用模型。

## Decision points

- 无需再决定例外完整性标准。拥有者已拒绝用标点或整句禁令代替语义核对。
- 是否给两个新码补专用详情句，不改变行为。建议补，但不作为阻塞项。

## Bounded questions

- 无。在拥有者跑完上述回归之前，不需要会议再改源码。
