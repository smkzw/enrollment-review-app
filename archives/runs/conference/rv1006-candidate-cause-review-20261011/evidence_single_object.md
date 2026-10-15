我先按会议只读边界核对上下文和主会场计划，再针对已拒候选、兄弟证明和发布资格做证据审阅。上下文要求只核对当前差异和受影响定义。我先看工作区差异，再读候选对齐、失败分类和独立步骤限额的实现。差异集中在三处。接下来核对失败分类、独立续跑和真正时间歧义是否仍走原路径。# Conference Output: rv1006-candidate-cause-review-20261011 - evidence_single_object

## Output

未做最终验收。当前差异没有把这批结果写成可发布输出，也没有改独立续跑的两个错误码和上限 2。但它把「已拒候选」收成终态 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 时，会丢掉同批真正的时间歧义，并把资料政策失败一并改记。服务层因此可能把原先会停住的步骤，算进允许继续的语义失败。

### 证据

只读了当前工作区差异和上下文点名的定义。未跑测试，未读临床、tmp、数据库、环境，未改文件，未上网。`git diff` 里与本目标有关的只有三处：`app/agents/protocol_control_deconstructor.py`、`app/services/protocol_control_execution.py` 的一行版本串、`tests/v2/protocols/test_slice58c_control_deconstructor.py`。`app/workflow/runner.py` 无差异。

`protocol_control_deconstructor.py` 在 `temporal_unresolved_indexes` 非空时，先收集与这些下标相交的 `alignment_failures`，以及 `decision == "incomplete"` 的候选。任一成立就追加终态 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 并 `return`，状态是「需要核对」，不写 `final_output`。两者都不成立时，仍 `raise SourceTemporalScopeUnresolved`（约 10503–10556 行）。

`alignment_response is None` 的传输、身份、预算失败仍在约 10442–10463 行返回，终态保持原失败码。有响应体但整段核对抛错时，只记一条 `SOURCE_CANDIDATE_ALIGNMENT_INVALID`，并不返回。

`bind_partial_candidate_alignment` 把异常的 `error_detail` 展开进失败字典（`protocol_control_candidate_alignment.py` 约 780–789 行）。`EvidencePolicyCheckError.error_detail["code"]` 是 `EVIDENCE_POLICY_UNJUSTIFIED`，会覆盖原来的 `SOURCE_CANDIDATE_ALIGNMENT_INVALID`。同一文件里，既有政策核对路径明确不把政策失败写成语义未核（解构器约 7753–7758 行）。

已通过的 `fully_expressed` 会先从 `temporal_unresolved_indexes` 去掉，并写成 `semantically_aligned`。新返回用 `checkpoint_alignment()`，`require_positive=False`，已核兄弟和未完成项都可以留在对齐记录里，但未完成项不会被标成已对齐。

`_INDEPENDENT_DEEP_READ_POLICY` 仍是这两个码，上限 2：`PROTOCOL_CONTROL_SOURCE_TARGET_REVIEW_UNRESOLVED`、`PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`（`protocol_control_execution.py` 263–270 行）。Runner 的 `_continue_independent_after_failure` 只认 payload 里的这组码，逻辑未改。

服务映射只看 `attempts[-1]`。`TEMPORAL_SCOPE_UNRESOLVED` 不在 `source_review_failure_codes` 里；对不上时错误码落到 `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`。新终态在这组码里，会变成 `PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`（约 4815–4867 行）。这个码在独立续跑白名单内，`DEEP_OUTPUT_INVALID` 不在。

`_preserved_negative_alignment_proof` 要求终态就是语义未核、下标与 `incomplete` 项完全一致，且失败单元已经在 `reviewed_semantic_repair_unit_ids` 中（约 3254–3298 行）。证明不成立才调用 `restricted_batch_from_review`。时间限制证明要求终态类恰好是 `TEMPORAL_SCOPE_UNRESOLVED`、`json_path == "/items"`、`retry_class == "temporal_scope_review"`（`protocol_control_restricted_source.py` 168–172 行）。整单元限制只接受未决或时间歧义（459–464 行）。新诊断的 `json_path` 是 `/source_candidate_alignment/items`，且 `build_result` 不会因为这次返回而写入修复单元。

`_resumable_saved_candidate_alignment` 默认只要 `fully_expressed`（2217–2262 行）。`_execute_deep` 把这个结果交给 Runner。测试里「不再调用读者」是直接把完整对齐对象传进 Runner，并把它的读者设成 `None`（`test_slice58c_control_deconstructor.py` 约 15817–15827 行）。

版本串只多了 `candidate-time-failure-cause/v1`（execution.py 2157 行）。跨作业复用可以用 `_same_deep_components_with_current_gate` 忽略单独的 `validator_version` 差异。同作业诊断续跑在约 4504 行用整份 `component_identity` 做相等比较。

### 推论

新鲜拒绝不再被改记成 `TEMPORAL_SCOPE_UNRESOLVED`。具体失败仍留在前一条 `SOURCE_CANDIDATE_ALIGNMENT_INVALID`，并复制进终态的 `alignment_failures`。这批没有 `final_output`。时间证明器认不出这条新终态，整单元限制也不收它。按现在的分支，这条路径不会走 `_complete_restricted_deep_source`，本批不会因受限来源而成功落盘。

已核兄弟仍留在对齐和覆盖里，覆盖状态是 `semantically_aligned`，未完成兄弟保持 `candidate_linked`。这只说明检查点保留了兄弟，不是发布。

没有比较拒绝、也没有 `incomplete` 项时，仍抛时间歧义。传输层在没有响应体时不会走进新分支。独立策略常量本身没有被改写。

新终态改变的是服务怎么归类。原先时间终态对不上来源核对码，步骤失败码是 `PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID`，Runner 不继续其他深审步骤。现在终态落在白名单内，只要该作业冻结了独立续跑，且同类新失败还不满 2，其他 `deep_` 步骤可以继续。作业最终仍会因本步失败而不能整作业发布。限额数字没变，但这一类失败从「停住」变成「占用一个续跑名额」。

若 `temporal_unresolved_indexes` 里同时有已拒或不完整项，以及从未进入比较的时间项，新分支只报告相交的那一部分并返回。其余时间项不会再抛 `SourceTemporalScopeUnresolved`，也不会出现在终态 `statement_ids`。服务只看最后一条，整步被当成可续跑的语义失败。坏的时间来源还在未发布的批里，但终态范围已经把它漏掉。

有响应体的整段核对失败也一样。前面那条失败没有 `error_detail`，新分支若看到保留的 `incomplete` 兄弟，就以那个兄弟为终态返回。刚失败的那条陈述不在终态范围内。

资料政策失败会被同一分支收成语义未核。嵌套的 `alignment_failures` 里仍可能是 `EVIDENCE_POLICY_UNJUSTIFIED`，但服务使用的终态类不是它。既有政策路径禁止这种改记。结果是坏的政策来源不再作为终态停住，而可以占用语义续跑名额。

新鲜拒绝的对齐对象可以是 `None`，测试也这么断言。否定证明要求有 `incomplete` 项和已用过的修复单元，这条新返回对不上。因此 `preserve_unresolved` 不会把这次失败当成「不再读取」的已耗尽证明。服务续跑还会先丢掉 `incomplete`，再在读者仍可调用时重新核对。测试里的「无新读者」没有经过 `_execute_deep`。

版本串不会让旧的成功结果因为仅校验版本变化而被重新发布。同作业上已保存的诊断会因身份不相等而变成 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`。这个码不在两个续跑码里，会停掉独立续跑，但不会发布。

### 建议

不要在相交集合非空时整段返回。把下标拆开：只有确实被拒绝或标成 `incomplete` 的下标可以记语义未核；其余仍在 `temporal_unresolved_indexes` 里的下标继续抛 `SourceTemporalScopeUnresolved`。终态若必须只留一条，时间范围不能被语义诊断盖掉。

`failure["code"]` 在展开后若是 `EVIDENCE_POLICY_UNJUSTIFIED`，不要改记成 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`。保持已写入的政策失败为终态，与约 7753 行的区分一致。

`alignment_response` 已经存在、但整段绑定或解析失败时，按无响应那条路径一样立即返回。不要再落到后面的语义或时间分支。

不要为了让否定证明通过而补写 `reviewed_semantic_repair_unit_ids`。修复单元只能表示修复真的跑过。在证明被有意放宽之前，服务层「保存的未完成比较不再调用读者」不成立；Runner 直传对齐对象只覆盖直接恢复。

若 Codex 接受这类失败占用语义续跑名额，应写明：仅当终态范围与拒绝或不完整项完全一致、且不含政策失败和剩余时间项。否则终态应回到不会续跑的失败码。

### 不确定性

未执行测试，也没有把新的 Runner 结果送进真实的 `_execute_deep`。上面关于续跑码、受限批次和证明失败，是按当前分支读出来的，不是运行观测。

未核对产品运行 `831db58a` 的三份原始响应。上下文所说的兄弟分支和数值关系，不能在本次用运行记录复核。

未证明所有 `additional_requirement` 都会让 `_restricted_statement_batch_from_review` 返回空。当前读到的条件是：新终态不会产生时间下标，因此「补充要求且不在时间下标中」会让该函数返回空。若将来的核对决定里不再有补充要求，这个推断要重读。

### 异议、决定点和问题

最大的异议是：切片测试能证明 Runner 不再写 `TEMPORAL_SCOPE_UNRESOLVED`，但不能证明服务消费者仍停在原拒绝、不扩大续跑。终态码一变，Runner 的白名单就会把原先的 `DEEP_OUTPUT_INVALID` 当成允许继续的语义失败。

第二是混合范围。一个已拒候选足以让同批另一个真正的时间歧义从终态消失。这不符合「没有比较拒绝时仍是时间歧义」，因为有拒绝时，没有拒绝的那些下标也被一起吞掉。

第三是政策失败。同一段新代码把 `EVIDENCE_POLICY_UNJUSTIFIED` 收成语义未核，现有政策路径明确不这么做。

请 Codex 决定一件事：已拒或未完成、且下标集合与时间未决集合完全一致时，终态改成 `PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 并允许最多两个独立续跑，是否就是这次要的行为。若是，剩余时间项和政策失败也不能进入这个码。

安全的临时路径：混合范围、政策失败、以及有响应体的整段核对异常，都不要走这次新增返回。只保留「时间下标全集等于拒绝或不完整下标」的那一支，直到服务层对终态码有对应断言。
