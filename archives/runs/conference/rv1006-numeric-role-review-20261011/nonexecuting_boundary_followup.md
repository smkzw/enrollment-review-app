当前产品仍拒绝角色不同的数字。我只读 HEAD 上的现有合同，看坏候选能否丢弃，同时把忠实于原文、且不执行的要求留成软件能力缺口。现有合同里有没有一条小路径，能丢掉未对齐的候选、同时把原文完整要求留成软件能力缺口，我先只读当前 HEAD 的生产者和直接消费者来核对。# Conference Output: rv1006-numeric-role-review-20261011 - evidence_single_object

## Output

当前 HEAD `f25f7eeb667cae0570223b739dc349e278341876` 上，没有一条现有合同能在丢掉这条未对齐候选的同时，把原文完整、无歧义的要求保存成 `limitation_kind=consumer_unavailable` 的非执行软件能力缺口，并让已证明正确的兄弟要求保持原样。第一处缺失的证明是：没有任何生产者会为“原文解释已完成、`unresolved` 为空、候选未获得对齐”发出一份可被现有受限消费者接受的类型化能力失败。本结论是工程阅读，不是临床、监管或最终用户验收。合成句 `复核时可免予14天内的血常规、18导联检查。` 只用于说明数字角色，不作为项目句式，也不据此放宽测试。

### Findings

数字角色失败仍停在候选语义，不进入软件缺口。`validate_candidate_alignment` 用整句数字集合比较。同一句里的 `14` 与 `18` 使 `len(numbers) != 1`，`fully_expressed` 会以 `numeric_relation_unverified` 失败（`protocol_control_candidate_alignment.py` 1126–1132）。`bind_partial_candidate_alignment` 把该失败记为 `SOURCE_CANDIDATE_ALIGNMENT_INVALID`，且不把失败项写入已绑定条目（761–807）。

带天数的补充要求会进入 `temporal_unresolved_indexes`，因为 `source_requires_temporal_resolution` 匹配 `\d+(?:天|日|周|月|年)(?:内|以上|以下)?`（`protocol_control_source_interpretation.py` 2990–3001）。单访视编译器对这类陈述直接跳过（`protocol_control_deconstructor.py` 10121–10124）。若这些时间序号全部被 `SOURCE_CANDIDATE_ALIGNMENT_INVALID` 或 `incomplete` 覆盖，解构器在 10561–10594 记录 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED` 并返回。同段注释写明：候选含义失败不是原文时间歧义。此处不抛出 `SourceTemporalScopeUnresolved`。

`event_date` 加 `before/14` 也没有既有对齐许可。`_matches_time_anchor_direction` 只在时间词不含数字、方向唯一、且上下界全部为空时，允许 `event_date` 配合 `interval_condition`（299–324）。带 14 天边界的候选不走这条分支。

现有三条 `consumer_unavailable` 生产路径都不接受这份回执。

- `_restricted_capability_batch`（230–342）只保留已证明的小时或分钟缺口。最后一次尝试的错误类必须包含 `TIME_PRECISION_UNSUPPORTED`，且只能再加 `PUBLICATION_GATE_REJECTED`。门禁问题必须全部是该码。失败候选只能占一个来源单元。该单元只能有一条陈述，`quoted_text` 必须等于单元 `excerpt`，`scope_quote` 必须为空，并且 `intraday_time_fragments` 非空。限制说明固定为小时或分钟精度。解构器只在错误类恰好是这个时钟集合时写入 `capability_wire`（11642–11659）。`SOURCE_NUMERIC_SEMANTICS_UNVERIFIED` 等数字类会停止自动修订，但不写 `capability_wire`。`intraday_time_fragments` 只识别小时、分钟（`source_time_fragments.py` 86–102）。“14天内”没有这类片段。
- `_temporal_restriction_indexes`（157–227）要求最后一次错误类恰好是 `TEMPORAL_SCOPE_UNRESOLVED`，明细的 `code`、`json_path="/items"`、`retry_class="temporal_scope_review"`、有序且不重复的 `statement_ids`、相同的 `affected_dependents` 和单元片段 `source_refs` 全部一致。陈述的 `unresolved` 必须为空，并已通过 `requires_temporal_resolution`。整单元路径还要求动作功能里有 `action`、没有 `definition`，语气是 `required` 或 `prohibited`，或满足狭窄的建议项条件。陈述级共存还要求 `source_statement_is_standalone_action`：`decision_functions == ["action"]` 且语气为要求或禁止（`protocol_control_gate.py` 5125–5128）。
- `_whole_unit_restriction`（449–465）只接受错误类恰好为 `{SOURCE_TARGET_REVIEW_UNRESOLVED}` 或 `{TEMPORAL_SCOPE_UNRESOLVED}`。没有未决复核项、也没有上述时间证明时，函数返回空。它的注释写明：不能把缺少对应关系改写成原文歧义。

`restricted_batch_from_review`（895–938）在 `capability_wire` 为空时，只让错误类落在候选语义、目标复核未决、时间范围未决三者之内的结果继续。语义失败会进入 `_restricted_statement_batch_from_review`。那里的 `additional_requirement` 只有在序号属于时间证明集合时才放行（724–727）。语义失败不会产生该集合，因此返回空。随后的整单元函数又因错误类不符返回空。多数字夹具已经断言这个结果：`restricted_batch_from_review(...) is None`（`test_slice58c_control_deconstructor.py` 15997–16005），并且 `continue_atom` 不会被调用。

执行层把失败证明和受限保存分开。`_preserved_negative_alignment_proof`（3359–3413）只保存已耗尽的候选失败，`adopted` 为假；它要求错误类恰好是候选语义未核、陈述 `unresolved` 为空，且序号等于已绑定的 `incomplete` 项。`fully_expressed` 的数字失败不会留下 `incomplete` 项，所以这份证明不成立。执行器仅在该证明为空时才调用 `restricted_batch_from_review`（4922–4926）。两条路都不产生受限陈述。失败码是 `PROTOCOL_CONTROL_SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`。`capability_wire` 存在但生产者返回空时，失败码是 `PROTOCOL_CONTROL_CAPABILITY_RESTRICTION_UNPROVEN`（4986–4989）。

已证明的兄弟不会被这条失败改写。`test_partial_candidate_alignment_keeps_verified_pair_when_sibling_temporal_fails` 中，负向或无效正向回答保持兄弟为 `semantically_aligned`，最后错误是候选语义未核，且不出现 `TEMPORAL_SCOPE_UNRESOLVED`。这是失败诊断里的原样保留。它不把本句拆成受限陈述，也不发布整批。

时间消费者本身仍不执行。`calculate_control_operand` 对 `interval_condition` 返回 `interval_calculation_unsupported`，`accepted` 固定为 `False`（`control_operand_calculation.py` 21、96–102）。带 `control_origin` 的期望在窗口计算之前返回 `PENDING_CONTROL_APPLICABILITY`（`evidence_expectations.py` 253–260）。这是软件接线事实。它不是方案缺少锚点，也不是受试者记录缺失。

对象数字检测不能补上这个消费者。即便数字角色被分开，`event_date` 加有界 `before/14` 仍不符合现有无数字、无边界的对齐分支；操作数计算仍是 `UNKNOWN` 且不可接受。在本次交付冻结中单独实现它，是超出当前失败回执的扩展。先前提出的出现位置证明也尚未实现。

### Inferred limitations

任务上下文已经识别，只说明这句不是“没有任务位置”。它不提供命名锚点，也不授权 `event_date`。候选上的语义许可原子没有改变整句数字集合。

陈述级共存对语气和功能有额外门槛。合成句的许可形状没有在本次阅读中被证明为 `decision_functions == ["action"]` 且语气为要求或禁止。即便将来出现合法的时间证明，这句话本身仍可能过不了 `source_statement_is_standalone_action`。这是门禁形状，不是医学分类。

同一单元里的兄弟只有在受限序号已经属于未决集合或时间证明集合、区间逐字不相交、动作自包含，且候选只引用兄弟原句时才能留下（`_coexisting_statement_proofs` 345–446）。候选若引用受限原句，测试 `candidate_cites_restriction` 要求整批受限结果为空。共享前缀会改走整单元保留，兄弟不再可执行（`shared_scope`）。单句里的两个数字不是两个可拆陈述。

`_preserved_temporal_restriction_proof` 还要求受限批没有候选、也没有独立区间证明（3329–3334）。它保存的是整批不可执行，不是“丢掉坏候选、发布好兄弟”。

本次没有读取真实任务回执，因此不知道该候选的覆盖状态是否恰好为单一 `candidate_linked`。按当前分支，只要对齐失败覆盖了全部时间序号，结果就是语义失败。只有在对齐失败没有覆盖该序号、复核决定是 `additional_requirement`、并且编译器实际抛出了完整时间明细时，现有时间受限生产者才可能合法运行。所给事实是候选没有获得对齐证明，不是这份时间明细。

### Recommended implementation

这一冻结里不改生产者，也不实现对象数字检测。这句保持现有未发布失败：`SOURCE_CANDIDATE_ALIGNMENT_INVALID` / `numeric_relation_unverified`，批次级为 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`，`final_output` 为空。不写 `capability_wire`，不补 `unresolved`，不把错误类改成 `TEMPORAL_SCOPE_UNRESOLVED` 或 `SOURCE_TARGET_REVIEW_UNRESOLVED`，不屏蔽数字，不自动填写 `event_date`。已经绑定并通过重核的兄弟对齐保持在原有 `partial_wire` 中，不被本句失败改写，也不借本句失败发布。

在现有合同上，要让软件能力缺口变得合法，必须先有一份现在不存在的类型化失败。它要同时证明：原文陈述完整、`unresolved` 为空、来源片段和摘录就是该单元原文、候选对齐失败只说明该候选不能采用、并且缺口是当前消费者不能执行这个有界日窗口。现有消费者只认三份证据：小时或分钟的 `TIME_PRECISION_UNSUPPORTED` 加 `intraday_time_fragments`，或完整的 `TEMPORAL_SCOPE_UNRESOLVED` 明细，或带具体未决方面的目标复核未决。这份日窗口回执四者都不满足。第一段缺失代码在解构器 10561–10594：它发出的是候选语义失败。第一个因此无法保存缺口的消费者是 `restricted_batch_from_review`。

### What remains unproven

测试本轮没有执行。真实批次的覆盖状态、复核决定、错误明细和候选原文没有读取。合成句没有被当成夹具，其 `force` 与 `decision_functions` 是否满足独立动作门槛没有证明。`interval_calculation_unsupported` 与 `PENDING_CONTROL_APPLICABILITY` 没有在受试者资料上运行。没有人验收这句话的临床含义，也没有人判定受试者记录是否存在。

### Objections

把坏候选改名为受限陈述，没有来源证明。`RestrictedProtocolControlStatement` 保存的是原文摘录和解释字段，不含义务表达式（`protocol_controls.py` 2217–2228）。生产者不会把 `event_date` 候选抄进受限记录。

把语义失败改记为原文歧义，与解构器 10567–10569 和来源疑问提示相反。提示要求程序尚不能消费时不要写成原文 `unresolved`（`protocol_control_source_interpretation.py` 805–806、832）。

用负向对齐证明充当能力缺口，与 `_preserved_negative_alignment_proof` 的职责相反。该证明的 `adopted` 为假，而且不创建受限陈述。

用对象数字检测代替时间消费者，不能让 `accepted` 变成真，也不能让 `event_date` 通过现有无边界分支。

### Decision points

交付边界保持当前拒绝。不新增受限通道，不实现数字角色检测。

已证明兄弟留在失败诊断的原证明里。它们不因本句被拆成可发布控制。

日后若要保存这句非执行要求，先要有一份不同于上述三类错误的类型化证明，并经过单独批准。本次不设计该证明。

### Bounded questions

无。所给事实已经足以判断现有合同走不通。真实回执里的覆盖状态只会区分“语义失败”与“另一份尚未出示的时间编译明细”，不会让当前这份未对齐候选变成合法的 `consumer_unavailable`。
