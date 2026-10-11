先前把这句的时间消费者说成 `interval_condition` 并不适用于当前候选。我先按 HEAD `5c63ba1f` 核对确定性 `source_validity` 路径，以及数字角色门禁是否在锚点与阶段证明之前就拒绝。上一份报告把时间原子错记成区间条件。我先核对当前 HEAD 上受限保留路径和数字角色守卫，再给出这一交付窗口的有限建议。# Conference Output: rv1006-numeric-role-review-20261011 - evidence_single_object

## Output

在 `5c63ba1f04fface7d47a6e45a3551de91469b938` 上，这条合成句仍不能采用，也不能改记为 `consumer_unavailable`。上一份报告用 `interval_calculation_unsupported` 说明本候选，这个引用是错的。本交付窗口只应做一件事：在现有对齐里增加一个失败关闭的数字角色核验，把四种角色拆开并给出分项失败原因。四项同时通过之前，它只产生更窄的修订反馈，不发表、不修复、不保留。

本报告不作临床、监管或最终验收。测试未运行。

### 更正

本候选的时间原子是 `determination_mode=deterministic`、`operation=time_constraint`、`operand_attribute=date_range`、`time_purpose=source_validity`。`calculate_control_operand` 只在 `time_purpose == "interval_condition"` 时返回 `interval_calculation_unsupported`（`app/projections/control_operand_calculation.py` 96–102 行）并提前返回。`source_validity` 不走该分支，而是调用 `evaluate_time_constraint`（117–120 行）。`ControlOperandCalculation.accepted` 仍是 `Literal[False]`（21 行）。事件值或锚点缺失时，`evaluate_time_constraint` 返回 `UNKNOWN` / `date_or_anchor_missing`（`app/domain/expression.py` 344–352 行）。这两条边界保持不变。`interval_calculation_unsupported` 不能作为本候选的证据。

“没有现成生产者能把被拒候选改记为 `consumer_unavailable`”在本 HEAD 上仍然成立。它不是把数字集合守卫无限期留在原地的理由。

### 证据

合成句只作形状，不作项目专用模式：`复核时可免予14天内的血常规、18导联检查。` 功能为 action 加 exception，语气为 descriptive，原文 unresolved 为空。日期有效性原子与语义许可原子各自保留整句和正确引用。有效性原子为 `event_date` / `before` / `upper_bound_days=14` / inclusive；证据政策重复该约束。批次里冻结了标签为 `18导联检查` 的必做流程目标及其原生摘录和来源引用，候选显式链接该目标。

直接挡住四项区分的是对齐里的全数字集合守卫，不是区间消费者。`_NUMBER.findall` 在整句上取集合（`protocol_control_candidate_alignment.py` 157、1063 行）。比较词表（151–156 行）不含“内 / 以内”。因此本句数字集合为 `{"14","18"}`，方向为空。1126–1132 行在重复次数未保留、且原生访视捷径不成立时，只要不是“恰好一个数字、一个方向、且已有谓词”，就以 `relation_unverified=True` 抛出 `CandidateNumericAlignmentError`。该守卫不读出现位置，不读冻结目标，也不读时间窗。本文件对 `known_procedure_targets`、`catalog_item_id`、`cross_source` 零引用。

同一函数里，1043–1056 行的定义、例外和禁止检查排在数字守卫之前。例外功能若缺少 `exception_words`，或候选自带 `exception_expression`，会先以“未明例外或独立例外层”失败。descriptive 本身没有单独拒绝；只有 `prohibited` 在 1049–1054 行有专门检查。角色核验不得跳过 1043–1056 行。

四种角色在现有代码里已经分开，只是集合守卫在它们之前失败：

1. 出现位置上的冻结对象名。`KnownRequiredProcedureTarget`（`protocol_controls.py` 2447–2477 行）冻结 `catalog_item_id`、标签、访视、审核阶段、来源定位，以及与定位一一对应的摘录。标签不必是摘录子串。`target_action_established`（`protocol_control_source_interpretation.py` 2987–3002 行）只证明整句出现在某段摘录中，或动作种类被覆盖；它不证明某一个数字出现在哪一个跨度里。整段标签含有数字，不能证明句中每一次数字出现都属于该对象。`14` 不在 `18导联检查` 内。
2. 真正的阈值、剂量或次数。现有路径要求一个比较方向加一个谓词，或无比较的动作次数加重复方案（1069–1078、1143–1156 行）。发布门 `_check_evaluation_numeric_sources`（`protocol_control_gate.py` 4274–4321 行）只检查带数值的谓词；纯时间约束原子因 `predicate is None` 被跳过。同一摘录里的数字个数多于谓词数值时，门返回 `SOURCE_NUMERIC_SEMANTICS_UNVERIFIED`。这仍不是按出现位置记账。
3. 原文绑定的时间窗数量、单位、方向和是否含边界。`_TIME_BOUND_SUFFIX_RE` 把“N天/日/周/月/年 + 内/以内”收成 inclusive 上界（317–320、3103–3110 行）。`upper_bound_days=14` 且 `upper_bound_inclusive=True` 能成为 `("upper", 14, "day", True)`；期望边界不是结构化边界的子集时失败为 `TIME_BOUND_COMPARATOR_MISMATCH`（3128–3132 行）。这段证明在发布门，对齐不调用它。它不证明锚点。
4. 显式锚点或阶段资格。`_ANCHOR_WORDS` 只有知情、筛选、基线、随机、首次给药、末次给药、研究结束（162–165 行）。“复核”不在其中。`event_date` 只在无数字、无边界、语义 `interval_condition` 的分支被当作来源表示（306–317 行），注释写明既有区间消费者将该能力缺口保持为 UNKNOWN。该分支不覆盖本候选。`review_node_date` 只在解释澄清区的 `anchor_resolutions` 绑定当前父规则、且原子原文是未命名“N天/周/月/年内”时合法（`protocol_deconstructor.py` 459–472 行）。澄清区不存在、父规则未绑定或来源定位不符时，不得使用它，也不得猜测命名锚点。本句解释完整且 unresolved 为空，因此这条澄清路径不可用。发布门对任何非空锚点放行，包括 `event_date`（3309–3311 行）；唯一额外拒绝是把筛选日猜成首次给药或随机（3312–3320 行）。非空锚点不是锚点证明。补充流程阶段核对要求恰好一个必做目标、受影响冻结节点、执行阶段一致，以及 `decide_at_node` 与证据 `due_stage`（4083 行起）。冻结标签加候选链接不是阶段证明。结果有效期还要求一条指向必做流程的补充关系，否则 `RESULT_VALIDITY_PROCEDURE_TARGET_MISSING`（4244–4257 行）。

锚点生产者不注入本候选所需的键。`subject_anchor_dates` 只给出非空的 `screening_date`、`icf_date`、`first_dosing_date`、`birth_date`，以及可选的 `review_phase_anchor_date`（`subject_dates.py` 171–189 行），没有 `event_date`，也没有 `review_node_date`。操作数计算只读冻结 episode 的 `anchor_dates`（`control_operand_calculation.py` 47、67、119 行）。`AnchorType` 注释写明 `review_node_date` 由调用方按 episode 注入；未注入时求值保持 `date_or_anchor_missing`（`enums.py` 55–62 行）。没有任何生产者把“复核时”或复查日期写成 `event_date`。

既有受限消费者不能保留这句完整原文。

- `_temporal_restriction_indexes` 要求末次错误类恰好是 `{TEMPORAL_SCOPE_UNRESOLVED}`，且详情码、路径和 `retry_class` 匹配（`protocol_control_restricted_source.py` 171–176 行）。非整单元路径还要求 `source_statement_is_standalone_action`：`decision_functions == ["action"]` 且语气为 required 或 prohibited（`protocol_control_gate.py` 5125–5128 行；受限生产者 220–228 行）。整单元的 `source_action` 同样要求 required、prohibited，或“必做单元中的 recommended”（209–223 行）。本句是 action 加 exception，语气是 descriptive，两边都不符合。语句 unresolved 还必须为空，但这只是必要项，不是充分项。
- 对齐失败的短路明确不把候选含义失败写成原文时间歧义，错误类是 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`（`protocol_control_deconstructor.py` 10585–10612 行）。只有失败索引不能覆盖时间集合时才抛 `SourceTemporalScopeUnresolved`。
- `restricted_batch_from_review` 允许该语义错误类进入（903–909 行），但有线分支只在 `temporal_indexes` 内接受 `additional_requirement`（726–729 行）。该索引在错误类不是 `TEMPORAL_SCOPE_UNRESOLVED` 时为空。无线分支要求每条语句 unresolved（736 行）。本句 unresolved 为空，两条都不成立。
- `_whole_unit_restriction` 只接受末次错误类恰好为 `{SOURCE_TARGET_REVIEW_UNRESOLVED}` 或 `{TEMPORAL_SCOPE_UNRESOLVED}`（465–467 行）。语义未核失败进不去。`consumer_unavailable` 只给引用扩展、已证明的时间索引或对应关系缺口（615–616、849–850 行），不给对齐失败。
- `_restricted_capability_batch` 要求 `TIME_PRECISION_UNSUPPORTED`，且该句含小时或分钟片段（247–248、304–316 行）。限制文案是“当前系统尚不支持原文所需的小时或分钟精度计算”。“14天内”没有时分片段。`source_requires_temporal_resolution` 对 `\d+天内` 为真（3005–3012 行），该布尔值本身不是保留证明。

局部修订允许名单只有 `numeric_predicate_missing`、`repeat_scheme_missing`、`source_condition_unrepresented`，且恰好一条原子路径（10772–10775 行）。`numeric_relation_unverified` 不在其中，因此不会调用 `continue_atom`。证据政策只在 `fully_expressed` 时比较草稿里的 `(validity_status, validity_constraint)`（898–928 行）。政策与草稿一致不解释义务数字，也不证明锚点；不一致则是 `value_mismatch`，不能当完整表达。

`control_origin` 的期望在来源有效期运算之前返回 `PENDING_CONTROL_APPLICABILITY`（`evidence_expectations.py` 253–268 行）。这是控制适用性尚未接入，不是本候选已经可计算，也不是患者记录缺失。

### 推断

集合守卫是直接阻塞的软件缺陷：它把对象名数字、时间窗数量和未证明的阈值收成同一个 `numeric_relation_unverified`，使后续分项修复无法开始。最小且仍然通用的修复，是在这条现有校验内按出现位置记账，而不是新框架、病种例外、目录标签屏蔽或数字谓词恢复。

一个有范围的角色核验是合理的，而且只能作为四项全部通过之前的失败反馈。它必须拒绝：

- 用整个标签或整个摘录包含关系代替一次出现跨度；链接的 `catalog_item_id` 与冻结来源引用不一致；同一数字字符串在对象名和阈值两处出现却被收成一个集合成员。
- 把时间窗数量当成临床谓词，或在没有比较方向、单位和重复方案时发明阈值或次数。
- 数量、单位、方向或含边界与该原子自身摘录上的既有后缀、前缀或日历边界子集不一致。复用门上的 `_TIME_BOUND_SUFFIX_RE`、`_TIME_BOUND_PREFIX_RE` 和结构化边界子集，不另写更宽的规则。该项通过也不接受锚点。
- 把 `event_date`、“复核时”、非空锚点、重复的证据政策，或冻结标签链接，当成命名锚点或阶段资格。命名锚点只来自 `_ANCHOR_WORDS` 与约束的实际对应。`review_node_date` 只沿用已经存在的澄清绑定。阶段只沿用现有补充流程核对。

四项都通过之前，核验不得给出 `fully_expressed`，不得设置 `capability_wire`，不得把混合角色失败放进上述修订允许名单，也不得调用 `continue_atom`。只有剩余问题恰好是既有的单原子 `numeric_predicate_missing`、`repeat_scheme_missing` 或 `source_condition_unrepresented` 时，才可以进入现有修订。窗口不匹配和锚点未证明都不是原子修订。

对本句，第 4 项失败关闭。`event_date` 不是复核日或复查日；“复核”不是命名锚点；完整且无 unresolved 的解释不能启动 `review_node_date`。第 1 项和第 3 项即使以后能被分项描述，也不能发布。第 2 项在本句没有比较词：没有剩余阈值要证明，也不得把“14天内”写成谓词。

既有类型化时间保留路径不能合法保留这句。原因是语句形状，不只是错误标签。即使另有生产者发出独立于坏候选的 `TEMPORAL_SCOPE_UNRESOLVED`，`_temporal_restriction_indexes` 仍会因 action 加 exception、descriptive 返回 `None`。把语义失败改记为时间歧义，或把 unresolved 写成非空，都是现有注释明确禁止的做法。新生产者因此在本窗口不必要，也不合法：它不能只靠换错误类就进入现有合同。与坏提案无关的软件缺口是，未命名日窗的锚点既不是 `_ANCHOR_WORDS`，也没有已批准的当前节点解析，而且受试者锚点生产者不发出 `event_date` 或 `review_node_date`。现有消费者还要求独立动作且语气为 required 或 prohibited。本句两者都没有。不新增限制种类，不改 `accepted`，不改缺失锚点的 UNKNOWN。

### 建议

本交付窗口只实现上述失败关闭的数字角色核验，放在 `validate_candidate_alignment` 现有数字段内，复用门的边界正则和冻结目标身份。不采用本候选，不补 `event_date`，不做目录标签屏蔽，不把 `numeric_relation_unverified` 放进修订允许名单，不把本句送入受限保留。`accepted` 保持 False。缺失锚点保持 `date_or_anchor_missing` / UNKNOWN。

这不是上一份“不要实现对象数字检测、留下未发表语义失败”的重复。对象数字检测本身仍然不能完成时间消费者；本窗口要的是分项失败，不是采用，也不是保留。

### 案例

正例。链接目标的原生摘录里，“18”只有一处出现且跨度恰好是 `18导联检查`，候选引用同一 `catalog_item_id` 和来源定位；“14天内”在有效性原子自己的摘录上匹配既有 inclusive 上界 14 天。核验仍须因锚点和阶段未证明而失败，不得 `fully_expressed`。对照句“年龄至少18岁”只有一个比较方向和一个谓词，继续走现有单数字路径，不要求流程标签。

语义变体。许可原子为 semantic，有效性原子为 deterministic `source_validity`，证据政策重复同一 `before/14/inclusive`。政策一致不满足数字守卫，也不证明 `event_date` 是复核日。政策与草稿不一致仍是 `EVIDENCE_POLICY_UNJUSTIFIED` 或 `value_mismatch`，不能反过来放过数字。

反例。同一句里既有 `18导联` 又有“低于18”，必须保持 `numeric_relation_unverified` 或更严，不得收成一个 `"18"`。`18导联检查` 不得解释 `14`。`event_date` 不得被当成复核日。仅有非空锚点不得通过第 4 项。descriptive 加 exception 不得被核验提升为 required 独立动作。

恢复。混合角色的 `numeric_relation_unverified` 留在修订允许名单之外。角色拆开后，只有剩余问题恰好是既有单原子谓词缺失、重复方案缺失或条件未表示，才进入现有 `continue_atom` 路径，并重新跑全部对齐。清除一个数字角色不清除未证明的锚点。后一份提案必须使用已证明的命名锚点，或已经存在的当前节点澄清绑定，然后整段重核。不得由核验器改写候选。

消费者。即便对齐以后通过，`calculate_control_operand` 仍不接受。冻结输入没有 `event_date` 时，结果仍是 `date_or_anchor_missing` / UNKNOWN，不是 `interval_calculation_unsupported`。`control_origin` 期望仍是 `PENDING_CONTROL_APPLICABILITY`。发布门可以接受任何非空锚点；该接受不是本报告的锚点证明，也不是采用理由。

### 第一处缺失证明

对这个阻塞缺陷，第一处缺失是出现位置证明：对齐在 1126 行之前没有把每个数字匹配绑定到链接冻结目标摘录中的一个跨度，也没有把另一个跨度绑定到该原子自身摘录上的既有时间窗边界。集合相等不能代替这两份证明。

对采用，第一处缺失是第 4 项：没有 `_ANCHOR_WORDS` 命名锚点，也没有已绑定的 `review_node_date` 澄清；冻结目标链接没有补充流程的阶段核对。`event_date` 不是这份证明。

对保留，第一处缺失是一份不依赖坏候选的类型化 `TEMPORAL_SCOPE_UNRESOLVED`，并且语句已经是 required 或 prohibited 的独立 action。本句的错误类是语义未核，语句形状也不符合。现有消费者因此返回空，而不是等待一个新标签。

### 仍未证明

- 活候选对象是否带有 `exception_words`。若没有，1046–1048 行会先拒绝，数字核验根本不会执行。本次只按给定形状阅读源码，没有看到运行中的候选。
- “18”在被链接的原生摘录里是否唯一，以及候选链接是否已经等于冻结的 `catalog_item_id` 和来源定位。输入形状如此描述，对齐目前不检查它。
- 该必做目标是否属于受影响阶段。本报告不从标签或“复核”推断阶段。
- 角色核验实现后的测试结果。本会话按边界没有运行测试。现有失败关闭用例仍应保持失败，包括 `test_action_completion_does_not_certify_numeric_details`、多数字 `numeric_relation_unverified`、`test_temporal_restriction_does_not_approve_unproven_error_ranges` 和 `test_capability_restriction_keeps_source_and_rejects_unproven_failures`。
- 患者是否另有复查日期记录。没有锚点生产者不等于病历缺失，也不等于方案没有锚点。

### 异议、决策与边界问题

异议：上一份把本候选放进 `interval_condition` 分支。该分支与 `source_validity` 的 `evaluate_time_constraint` 路径不是同一条。异议：用“不能改记为 `consumer_unavailable`”结束本窗口，会把集合守卫继续挡在四项区分之前。异议：目录标签屏蔽、自动 `event_date`、把描述性例外句提升为独立必做，或制造 unresolved，都会越过现有合同。

决策：授权的实现范围只有失败关闭的角色核验。采用、锚点注入和受限生产者都不在本窗口。`accepted=False` 与 `date_or_anchor_missing` 保持不变。

没有需要另作产品选择的问题。窗口边界不匹配可以沿用 `TIME_BOUND_COMPARATOR_MISMATCH` 的含义作为失败原因，但不得调用发布器。
