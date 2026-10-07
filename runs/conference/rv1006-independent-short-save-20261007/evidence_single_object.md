我先读会议上下文和主会场计划，再按指定定义核对短解释保存与门禁，不改文件、不跑测试。# Conference Output: rv1006-independent-short-save-20261007 - evidence_single_object

## Output

已读路径上，坏的第二条短解释不会抹掉已经单独编译通过的插入，发布结果仍然是「需要核对」。同一来源单元上的处置改写，以及非时间类失败后的整单元补入授权，仍会放宽采用边界。这不是临床验收。

## Evidence

对照 `c2df92bc`，变更只在四个文件：`protocol_control_deconstructor.py`、`protocol_control_stage_compiler.py`、`test_slice58c_control_deconstructor.py`、`test_protocol_control_agent_transport.py`。两个 service 文件无差异。未跑测试，未读临床原件。

调用顺序在 `ProtocolControlAgentRunner.run`：先非时间类 `simple_additional`，再 `temporal_unresolved_indexes`。每组内部沿用已按 `statement_index` 排序的复核。读成功后才成对进入 `short_reviews` 与 `short_responses`。传输在 `request_started and response is None` 时 `break`。单次读取上限是 3。

内容失败在随后的逐条 `compile_source_requirement_response` 中隔离。失败条目前只有非时间类才进入 `pending_additional`。`affected_dependents` 固定为 `[statement_index]`。通过子集才进入 `assemble_source_requirement_inserts`；`wire` 只在汇编和 `validate_source_target_review(remaining)` 都成功后赋值。汇编异常不写 `error_detail`，会话记在 `validated_short_responses[-1]`。

时间类剩余项在待补回退之前抛出 `SourceTemporalScopeUnresolved`，返回「需要核对」且不设 `final_output`。非时间类待补、且单元未与 `decision == "unresolved"` 相交时，抛出 `SOURCE_TARGET_ADDITIONAL_REQUIREMENT`，`allow_source_insert=True`，范围是该单元的全部 `source_span_ids`。

`assemble_source_requirement_inserts` 的授权集合是通过条目的 `structure_unit_id`。`_merge_source_candidate_insert` 把这些单元的处置改成 `OTHER_CONTROL_CANDIDATE`，并清空 official、procedure 链接和 notes。覆盖检查只要求本次 reviews 为 `expressed`。

`_coexisting_statement_proofs` 在处置已是 `OTHER_CONTROL_CANDIDATE`、引文不重叠、独立句已表达且候选未引用受限句时，可以给出同单元证明。`restricted_batch_from_review` 在证明失败或 `check_protocol_control_batch_candidates` 为真时返回 `None`，否则返回带原候选的 hydrated 结果。

提示词只增加了治疗期与研究期的来源区分，并要求不确定时保留 `unresolved_aspects`。编译器仍按原正则拒绝，不改写 `prospective_period`。时期错误带 `PROSPECTIVE_PERIOD_SOURCE_MISMATCH` 与 `/prospective_period`。动作拆分失败和版本不匹配不带 code、json_path。

`SHARED_PROHIBITION_REQUIREMENT_VERSION` 现为 v4，位于 `_deep_component_identity` 的 `compiler_versions`。不一致时 `_validated_deep_partial_source` 返回 `None`。`SOURCE_REQUIREMENT_FAILURE_POLICY_VERSION` 现为 v5，只进入 `protocol_control_agent_repair_contract_sha256`。有 `partial_wire` 而修复合同不一致时，先做当前校验，再返回 `None`。无 `partial_wire` 时仍可能走来源种子复用。

新测试 `test_invalid_short_sibling_cannot_erase_verified_insert` 把坏的共享禁止放在第二次调用，覆盖同单元与不同单元，以及错误时期、错误动作、错误版本。它断言第一条草稿保留、语句 0 已表达、语句 1 未表达、复核只剩索引 1、`restricted_batch_from_review` 为 `None`。只有错误时期断言了专用 code 和 json_path。相邻夹具位于 `test_slice58c_control_deconstructor.py` 的 10754 与 11306 行，本次未读函数体。

## Inference

生产故障那条路径是：阶段绑定短解释先通过，共享禁止因时期失败。坏项是时间类，不会进入整单元补入；已通过插入留在 `partial_wire`，批次不发布。坏的第一条如果是内容失败，读取循环仍会继续，因此不会挡住后面的独立调用。第一条传输失败、或第 4 条超出 3 次上限，则后面的合法调用不会发生。

同单元并不是因为另一条已经插入就被证明独立。合并按单元授权，会先改掉整个单元的处置。非时间类失败随后还能把该单元送回来源补入。新测试没有覆盖「坏的非时间类在前、合法时间类在后」，也没有覆盖单元上原来带有 official 或 procedure 链接的情况。`same_unit=True` 仍返回 `None`，只说明这个夹具没被采用，不能说明共存证明的接受条件已被关闭。

逐条时期失败能定位到语句索引、单元 spans 和 `/prospective_period`。同单元通常只有一个 span，source ref 不能把坏句和合法句分开。错误动作与错误版本会退回语句路径。汇编门禁失败没有结构化身份。失败尝试的 sha256 是异常字符串，原始回答在前一条 `parsed` 尝试里。

v4 编译器身份可以挡住这条恢复函数复用旧局部草稿。v5 失败政策本身不在组件身份里；有草稿时修复合同不一致也会拒绝复用，但无草稿的来源种子仍可复用。提示词句子本身不进入主模板哈希，本次靠版本常量生效。

## Recommendation

保留「逐条编译失败不丢已通过子集」，但授权粒度改到语句。只要同一 `structure_unit_id` 仍有未插入语句，就不要改该单元处置，也不要清空 official、procedure 链接或 notes。

非时间类短解释失败后，不要对仍含已保留兄弟候选的单元发出 `allow_source_insert=True`。停在逐条 `STAGE_BOUND_INSERT_INVALID`。汇编门禁失败同样停止，并写上全部参与汇编的 `statement_id`，不要只记最后一条会话。

不要自动改写模型给出的 `prospective_period`。提示词维持来源区分即可。

补这些反例，而不是把现有参数化计数当成通过：坏项在第一次内容调用、合法项在后一次，且同单元；非时间类坏兄弟不得触发整单元补入；两条各自编译通过但汇编门禁失败时，草稿与处置都不变；引文恰好分割同一单元时，`restricted_batch_from_review` 仍为 `None`；旧 v3 组件身份和旧 v4 修复合同不能恢复 `partial_wire`。正向只保留「原文明确治疗期仍可插入」和「原文明示研究期仍可插入」。

## Uncertainty

没有执行测试，也没有读 `_stage_bound_example`、`_require_resolved_source_target_review`、外层 source-insert 修复循环，以及 `protocol_control_execution.py` 2368 与 3143 附近的身份写回。因此不能断定这个夹具为何返回 `None`，也不能断定对齐把被拒绝的时间类标成 `semantically_aligned` 之后是否仍会被要求函数拦住。

## Objections

新测试的 `same_unit=True` 容易被当成同单元独立已获批准。它只固定了一个返回 `None` 的夹具，同时把 `affected_dependents` 锁成仅自身。

「有效子集仍走原批次门禁」只覆盖汇编那一次。门禁否决之后，非时间类条目会进入待补，并可能变成更宽的单元补入。时间类路径虽然不补入，但合并已经改写单元处置。

v5 与 v4 不是同一把锁。只升失败政策、不升共享禁止版本时，组件身份可以保持不变。

## Decision points

同单元尚有未插入语句时，是否还允许沿用历史合并规则改写单元处置并清空链接。建议不允许。

非时间类短解释失败后，是否仍进入 `SOURCE_TARGET_ADDITIONAL_REQUIREMENT`。建议在该单元已有保留候选时不允许。

被拒绝的时间类短解释如果旧候选已 `candidate_linked`，是否允许对齐把它移出 `temporal_unresolved_indexes`。建议不允许。

## Bounded questions

`_require_resolved_source_target_review` 是否会拒绝仍为 `additional_requirement`、但覆盖已被标成 `semantically_aligned` 的语句？这决定被拒绝短解释能否靠近发布。安全的临时路径是维持「需要核对」、不发布，并禁止同单元处置改写。

`protocol_control_execution.py` 2368 与 3143 附近若把旧 `partial_wire` 抄到新 `component_identity` 下，v4 与 v5 都挡不住。这两处是否纳入本轮？未纳入前，不以组件身份覆盖全部恢复路径。
