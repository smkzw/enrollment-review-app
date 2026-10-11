我先按会议只读边界读两份指定材料，核对候选数值里哪些是有源检查名、哪些是真实阈值、次数和时间窗。材料把失败定位在数字角色混用。我接着只读指定代码和测试，核对检查名数字、阈值、次数和时间窗是怎么被分开或混在一起的。数字校验把来源里所有数字收成一个集合。我继续看合同、时间消费者和现有正反例，确认名字里的数字会不会被当成阈值。# Conference Output: rv1006-numeric-role-review-20261011 - evidence_single_object

## Output

最高影响缺陷：`validate_candidate_alignment` 用整句数字字符串集合给数字分配角色。不同数字会被误拒；同一个数字承担两种角色时，又可能被一个比较谓词整句放行。目录标签遮蔽、以及“已有 `TimeConstraint` 再加一个语义免予原子”都不能当作证明。检查名数字即使被正确摘出，未命名近期窗仍然到不了可执行的受试者判定。本次不改代码、不跑测试、不读临床原答。

### 证据

核对入口在 `app/agents/protocol_control_candidate_alignment.py`。`_NUMBER`（157 行）是独立数字 token。1047 行把整句 `quoted_text` 收成 `set(_NUMBER.findall(source))`。比较方向只来自 `_COMPARISON_WORDS`（151–156 行）：`≥/≤/>/<` 及其中文同义。`以内`、`内`、`范围内` 不在表内。

因此现有分支是：

- 恰好一个数字、一个方向、没有谓词：`numeric_predicate_missing`（1058–1062 行）。
- 有数字，且不是已证明的单次复查，也不是“原生访视格全文入渲染、无 threshold、无方向”：数字个数、方向个数、谓词三者任一不满足就 `numeric_relation_unverified`（1110–1116 行）。
- 复查合同只在“恰好一个数字 + `{n}次` + 复查词、且无比较词”时成立（521–529、532–566 行）。
- `TimeConstraint`、原子 `kind`、流程目录标签都不参与这次数字归类。

`CandidateNumericAlignmentError` 的 `atom_paths` 只收录义务原子里、摘录含数字的路径（55–64 行）。`numeric_relation_unverified` 不在局部修复白名单。白名单只有 `numeric_predicate_missing`、`repeat_scheme_missing`、`source_condition_unrepresented`，且必须恰好一条原子路径（`app/agents/protocol_control_deconstructor.py` 10754–10768 行）。多数字夹具因此不调用 `continue_atom`，`final_output` 为空，`restricted_batch_from_review` 返回 `None`（`tests/v2/protocols/test_slice58c_control_deconstructor.py` 15890–16005 行）。

已有不安全例仍按这个集合语义成立（`tests/v2/agents/test_protocol_control_candidate_alignment.py` 1452–1488、1491–1517、1520–1537、946–989 行）：

| 原文形状 | 现结果 | 角色 |
|---|---|---|
| `给予3 mL药液，分为6个区域，避开2 cm范围` | `numeric_relation_unverified` | 剂量、分区、距离三个数字 |
| `给予3 mL药液` | `numeric_relation_unverified` | 单个剂量，无方向、无谓词 |
| `检查结果须在40 U/L以内` | `numeric_relation_unverified` | `以内` 不是比较词，单位也不是日历单位 |
| `检查结果须低于40 U/L` | `numeric_predicate_missing` | 有 `低于`，缺谓词 |
| `年龄至少18岁且不超过65岁` | `numeric_relation_unverified`，不进入谓词修补 | 两个阈值 |
| `年龄{大于等于/不小于/...}18岁` 且谓词方向一致 | 通过 | 单阈值 |
| 谓词方向或数值被改 | 拒绝 | 同一单阈值的反例 |
| `每3周…共12周` | 时间锚点失败 | 两个时间数字，不是可执行窗 |

时间侧已有一条很窄的通道，而且消费者明确不计算。`_matches_time_anchor_direction`（283–313 行）只在时间词不含数字、没有上下界、锚点为 `event_date`、方向唯一、`determination_mode=semantic` 且 `time_purpose=interval_condition` 时返回真。对应测试里，无界的“核查前”可以通过对齐，但 `_proposition_observation` 返回 `UNKNOWN` / `interval_calculation_unsupported`；`upper_bound_days`、改成 `screening_date`、方向反了，都在对齐层拒绝（844–888 行）。`app/projections/control_operand_calculation.py` 96–102 行对 `interval_condition` 同样直接返回该原因，且 `ControlOperandCalculation.accepted` 固定为 `False`（21 行）。

命名锚点的日历窗在发布门里已经有合同，对齐层没有复用。`app/protocols/protocol_control_gate.py` 317–320 行把 `N天/日/周/月/年` 加 `内/以内` 收成上界且含边界；3060–3132 行要求结构化边界与原文一致。2881–2932 行的免予绑定要求：同一义务组、摘录和 span 完全相同、`verify_result_validity` 携带 `time_constraint` 且 `time_purpose=source_validity`、`complete_or_verify` 不带时间约束、语义模式、`time_purpose=not_applicable`、原文有免予措辞且只有一个时间线索。这与解构提示里的双原子形状一致（`protocol_control_deconstructor.py` 2131–2136 行）。门对锚点只检查非空（2956–2959、3309–3321 行），`event_date` 不会在这里被拒绝；它只拒绝把首次给药或随机猜成 `screening_date`。

`KnownRequiredProcedureTarget`（`protocol_controls.py` 2446–2476 行）有 `label` 和可选 `source_excerpts`。校验不要求标签是来源摘录的子串。结果有效期原子还必须有指向 `required_procedure` 的跨源关系，否则 hydration 报 `RESULT_VALIDITY_PROCEDURE_TARGET_MISSING`（deconstructor 测试 1668–1707 行）。这条关系证明目录身份，不证明某个数字是检查名。

受试者投影没有把补充控制的有效期算成缺失或通过。`project_expectation` 在看到 `control_origin` 后直接返回 `PENDING_CONTROL_APPLICABILITY`（`app/projections/evidence_expectations.py` 250–269 行），早于后面的 `source_validity_window` 计算。`control_source_validity`（`app/domain/source_validity.py` 49–72 行）只按约束自己的 `anchor_type` 取锚点；锚点缺失时 `evaluate_time_constraint` 返回 `date_or_anchor_missing`（`app/domain/expression.py` 344–352 行）。`FrequencyHorizon` 明确禁止用 `event_date` 或 `review_node_date` 充当多期间范围（`rules.py` 222–225 行）。`AnchorType.EVENT_DATE` 的合同注释把它和“当前审核节点日期”分开（`enums.py` 55–63 行）。

资料政策里的 `result_validity_constraint` 是另一条字段（`control_evidence_policy.py` 22–34 行）。对齐只核对审核员填写值与草稿是否一致（alignment 882–913 行），不用它解释义务原文里的数字。

本次额外读取及原因：操作数计算、命题观察、时间求值、来源有效期、证据期望投影、发布门的免予与日历正则、解构器修复白名单、锚点枚举、证据政策合同、多数字修复夹具。用于判断“对齐通过后能否进入确定性消费者”。未读 `.env`、临床原文、模型原答和历史会议报告，未改文件，未跑测试。

### 推断

合成句 `复核时，9天内的18导联检查结果可免于重复检查` 会被收成 `{"9","18"}`，方向集为空，从而 `numeric_relation_unverified`。`9天内` 在发布门是含边界的上界，在对齐层只是一个没有比较词的数字。`18` 不会因为目录里有“18导联检查”就被摘掉。作者已经放上 `TimeConstraint` 和第二个语义免予原子，正好说明这两样目前改变不了这个集合判断。

若两个原子按门的要求共用整句摘录，两条路径都会含数字，`atom_paths` 长度为 2。即便将来把 `numeric_relation_unverified` 加进白名单，也不会进入“恰好一条路径”的谓词修补。这是应保持的限制：谓词修补器会把时间窗或导联数写成值比较。

集合语义还有一个与本次误拒相反的洞。`18导联检查结果须低于18` 的集合只有 `{"18"}`。只要存在一个 `lt` 谓词且值为 18，1110–1140 行可以放行，导联数和阈值被当成同一个数字。用“集合里任意一个谓词对上”来消除误拒，会把这个洞扩大。

`复核` 不在 `_ANCHOR_WORDS`（162–165 行）。把该窗写成 `screening_date` 或带上界的 `event_date`，都不能用现有无数字 `event_date` 通道解释。无数字通道的消费者结果仍是软件不会算区间，不是受试者缺一份记录。

目录标签不能做遮蔽键。标签不必出现在 `source_excerpts`，也可以由模型写成 `结果低于40 U/L` 或 `3 mL药液`。按标签删数字，会把上述不安全例放行。只证明链接了某个 `catalog_item_id` 也同样不够。

原生访视豁免（1110–1111 行）会在“全文入渲染、解释器没标 threshold、没有比较词”时跳过全部数字。它不是检查名证明。`3 mL` 若出现在这种格子里，现有代码不会走 `numeric_relation_unverified`。本次修复不能放宽这条豁免。

### 建议

最小且自洽的改法是第 (1) 种，但只处理“这一处出现的是检查名”；剩下的时间数字继续走已有时间合同。不能把检查名修复写成整句可执行。第 (2) 种只适用于仍须拒绝的残留。不要新增第 (3) 种宽松通道，包括整句逐字引用、语义断言、或因双原子存在就跳过数字核对。

具体边界：

1. 用 `_NUMBER.finditer` 保留每次出现的位置。角色判断按区间做，最后才对剩余出现重新取集合。
2. 只有同时满足下列条件的出现，才可标为有源检查名并移出数值集合：该片段在本句 `count==1`；片段等于所链接 `KnownRequiredProcedureTarget` 的某条非空 `source_excerpt`，而不是 `label`；目标 `source_span_ids` 与本句单元相交；候选已有指向该项目的 `required_procedure` 关系；片段内没有比较词、日历时长、`次`、以及 `mL`、`U/L`、`cm` 这类剂量或距离单位。同一数字在片段外的另一次出现必须留下。
3. 移出检查名后，剩余出现仍走现有三条之一：单方向且谓词的比较符、数值、单位和来源条款一致；或现有单次复查合同；或恰好一个门已经认识的日历边界，其值、单位和开闭与 `verify_result_validity` 原子的 `TimeConstraint` 一致，`time_purpose=source_validity`，锚点词来自原文里的 `_ANCHOR_WORDS`，同组免予原子满足 `_exemption_validity_is_bound_in_group` 的现有条件。
4. 剩余窗没有这些命名锚点，或锚点是 `event_date` / `review_node_date`：保持不采纳。原因要与 `numeric_relation_unverified` 分开，表示锚点未由原文命名，消费者对应 `interval_calculation_unsupported` 或 `date_or_anchor_missing`。不要把它送进 `continue_numeric_predicate`，也不要要求研究者补一份并不存在的锚点记录。
5. 检查名证明失败时，整句维持 `numeric_relation_unverified`，多数字夹具继续不调用修补、不产生 restricted batch。

这样现有反例仍有效：剂量与距离组合、单独 `3 mL`、`40 U/L以内`、`低于40` 缺谓词、`18且65`、错误方向、错误单位、只引用数字的 `source_clause`、`event_date` 带天数、把“核查前”改成筛选日，都因为没有合格的检查名摘录或没有命名锚点而继续失败。新的正例只应是合成的、证据闭合的句子：唯一来源摘录恰好是 `18导联检查`，其余单独的 `筛选前9天内` 与 `screening_date`、上界 9 日且含边界、`source_validity` 和已绑定免予原子一致。`复核时，9天内的18导联…` 在锚点仍是“复核”时不应成为正例。

同一数字两种角色的反例必须单独存在：`18导联检查结果须低于18`。只遮蔽检查名那一次出现后，剩下的 `18` 仍要有 `lt` 谓词；没有谓词则为 `numeric_predicate_missing`。禁止先收成集合再遮蔽。

患者流要分开写，不能算这次修复的完成。即便命名锚点的有效期原子通过对齐，操作数计算仍是 `accepted=False`；补充控制的证据期望在有效期计算前就返回“控制待判断”。无命名锚点的近期窗没有确定性消费者。软件不会把“可免于重复检查”算成跳过检查，这不是源文件缺失。

### 不确定

未看到被拒候选的原文、`time_words`、`decision_functions` 和两个原子的摘录。以上对“两条 `atom_paths`”和“解释器未把该句标成 `time_validity`”是结构推断：所有者观察到的是 `numeric_relation_unverified`，而该原因排在时间锚点循环之后；若 `time_validity` 已标上且时间词含数字，更早会抛出“时间锚点或方向未由原文逐项证明”。

未核实发布门在完整候选上是否还会用别的规则拒绝 `event_date` 加天数。对齐层这段代码和门的锚点非空检查之间，确实存在这个缝。

未跑测试。行号来自当前工作树阅读。

### 异议、决定点与给 Codex 的问题

异议：不要用目录标签或整句摘录做数字遮蔽；不要把双原子加 `TimeConstraint` 当成时间证明；不要批准 `event_date`；不要把 `numeric_relation_unverified` 接上现有谓词修补；不要把检查名修复说成患者流程已关闭。

决定点：未命名近期窗的下一编辑，只应更换拒绝原因并继续不采纳。是否另建“只展示、不产生真值”的非执行要求，是产品出口，不是这次数字归类能附带完成的。当前失败既不采纳候选，也不生成 restricted batch。

暂定路径：在未收到相反决定前，只实现按出现位置的检查名证明，以及原文已有命名锚点的既有日历合同；未命名窗保持不采纳并使用独立原因；同一改动不放宽 `event_date`，不改证据期望的提前返回。

有界问题：未命名窗的下一轮，是否只重分类型并保持不采纳？还是要同时增加一条无真值的审阅提示？这决定编辑范围。在回答前，不应为了让合成句 `复核时，9天内的18导联…` 通过而对齐层开例外。
