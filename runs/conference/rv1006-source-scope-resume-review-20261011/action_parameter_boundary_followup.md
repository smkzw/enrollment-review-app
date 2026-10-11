收到新的有界评审任务（C03 续审，只读、不委派、不落盘）。开始定位四个指定定义与相关测试。

定位完成。读取五个核心定义区段。

读取评估规格模型全文、数值/比较词定义与既有数值对齐测试。

读取数值/比较词定义、测试夹具、作用域引用校验与节点消费定义。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

C03 续审（只读；未改文件、未运行产品/模型调用、未读临床或私有运行；未委派）。本轮读取仅限被点名的定义与最近测试。**先给最高影响的结构性发现（代码事实）**，它决定 Q1/Q2 的答案：

> **`observation_policy.mode == "action_completion"` 与数值比较谓词在类型上互斥。**
> `app/domain/contracts/control_evaluation_spec.py:62-65`：`(determination_mode=="deterministic") ⇔ (operation is not None)`，且 `(operation=="value_comparison") ⇔ (predicate is not None)`；`:140-144`：action_completion ⇒ `determination_mode=="semantic"` 且 `repeat_scheme is None` 且无 `time_constraint`。合起来：**action_completion 原子在结构上不能携带 predicate、repeat_scheme、time_constraint**。因此“把结果阈值伪装成 action_completion”无法夹带比较谓词；反之“操作参数”也永远拿不到谓词。

---

### 1. 数值守卫是已证伪的正家族，还是正确的能力边界？

**结论（代码事实＋推断）：它是**正确的能力边界**，但同时制造了一个**真实的漏判家族**（对源含义完整、但无可核参数消费者的原句，无法给出“完整表达”判定）。二者不矛盾：拦住的是“无法核验”，不是“已证明有错”。**

**[代码事实] 守卫实文（`protocol_control_candidate_alignment.py`）**
- `1026-1041`：`numbers = _NUMBER.findall(source)`；`directions` 来自 `_COMPARISON_WORDS`（`:130-135`：≥/≤/>/< 及其中文同义，**不含“以内/范围内/正常范围”**）；`predicates = [atom.evaluation.predicate ...]`。`len(numbers)==1 and len(directions)==1 and not predicates` → `CandidateNumericAlignmentError`（reason `numeric_predicate_missing`，`:46-53`）。
- `1087-1114`：**只要源句有任意数字**（除 repeat 合同或 native 豁免），就要求“恰 1 个数、恰 1 个方向、且有 predicate”，并逐项核对 `comparator ∈ directions`、`str(value) ∈ numbers`、`unit ∈ source`、`exact_source_clauses` 逐字保留——否则 `raise "数值原文不能由模糊比较条件宣布完整"`。
- 现存的**类型化逃逸口只有两个**：① 复查次数合同（`:500-508` `source_declares_uncompared_action_count` + `:511-545` `_source_repeat_count_is_preserved`，把“N次”绑定到 `RepeatScheme` 并按源验证）；② native 表格动作豁免（`:1087-1088`：`native_visit_scope and source in rendered and "threshold" not in functions and not directions`，`:1087-1090`，`directions` 为空时可放行）。
- 守卫与 `decision_functions` **无关**：它对 `["action"]` 一视同仁；`decision_functions` 只用于 definition/exception/threshold/quantifier 等其它分支（`:1005-1011、1067-1081`）。

**[代码事实] 消费者一侧（患者证据资格）**
- `proposition_evidence.py:111-116`：action_completion 只核“原文是否明确记载操作已完成/未做/无法证实”，`action_quote` 必须逐字来自本配对；并明确“**操作完成不表示检查结果正常或资格合格**”。`:148-162` 只校验见证方向与引用归属。
- `qualified_proposition_evidence.py:105-116`：选择要求 `action_witness.status` 与记录一致 + 非空 `action_quote` + `scope_correspondence=="supported"` 且有 `scope_quote`；**没有任何参数（剂量体积/区域数/距离）核验**。缺少见证即 `action_completion_source_unverified` 拒绝。
- `control_evaluation_spec.py:95-103`：谓词只允许 `operand_attribute=="value"`、不得研究者判断、逐字保留比较原文——即 predicate 的语义是**患者结果值比较**，不是操作参数。

**因此**：
- 对合成手术句（3 mL、6 个区域、2 cm 以内，全部逐字保留在原子语句与语义命题，`decision_functions=["action"]`，显式 action_completion）：`numbers={3,6,2}`、`directions=∅` → 落到 `:1089` 的 `len(numbers)!=1` → 抛“数值原文不能由模糊比较条件宣布完整”。**即使只有一个数（如“接受3 mL给药”），零方向词也会被同一行拒绝。** 即守卫比主机描述更宽：**任意数字**都要求谓词路径（或 repeat/native 豁免）。这是**漏判**（源含义完整但不可判）。
- 这是**能力边界**而非缺陷：现有系统**没有任何消费者**能核验“剂量/数量/距离”这类操作参数——action_completion 消费者只核完成与观察范围；唯一的类型化数值表示是患者结果比较（predicate）。若只放开守卫，下游会把“已完成”的见证当作参数化要求的满足，属于越权。**区分：源含义（参数是否被忠实保留）≠ 患者证据资格（记录能否证明剂量/面积/距离）。守卫拦的是后者缺失下的前者宣告。**

---

### 2. 能否用现有“来源功能解释 / literal 保留 / 源绑定重审 / action_completion 消费者”做最小调整？缺什么？

**结论：不能。四个候选信号全部可被反例穿透（其中两个是结构性穿透），唯一缺的是“操作参数的源绑定类型化合同”。**

**逐项挑战（含反例）**
- **仅凭 `decision_functions`**：它是解释层标注，不是源证明。“检查结果须低于40 U/L”可以同样被标 `["action"]`——`validate_source_interpretation` 并不据此拒绝（守卫正是因此存在）。**否决。**
- **仅凭 policy mode（action_completion）**：结构性否决——该模式**禁止** predicate/repeat/time（`control_evaluation_spec.py:62-65、140-144`），所以任何“有 mode 就豁免数字”的规则，等于**保证**这些原子没有类型化比较；这正是 40 U/L 伪装所需的缝隙。**否决。**
- **仅凭 literal 保留（`source in rendered`、引句逐字）**：证明的是“抄写”，不是“类型”。“检查结果须低于40 U/L”可逐字复制进 proposition；且方向词表**不完整**（“以内/范围内/正常范围”不在 `_COMPARISON_WORDS`），所以“无方向词”也不是安全判据（反例：“检查结果须在40 U/L以内”）。**否决。**
- **仅凭源绑定重审/模型一致**：重审仍由同族模型给 `fully_expressed`，不增加源侧类型；“模型也同意”不是证据。**否决。**
- **现有 typed 先例说明“正确做法长什么样”**：复查次数走 `RepeatScheme` + `validate_repeat_source`（`:511-545`），native 动作走 `source in rendered + 无方向词 + 无 threshold` 的**受限**豁免（`:1087-1088`）。操作参数没有对应物。

**[建议] 缺的源支持类型化区分（精确表述，非本轮实现）**：一个**操作参数合同**（与 `RepeatScheme` 同级的既有类型化思路，不是新框架）：在求值规格上声明 `operation="action_parameter"`（或等价的最小类型），其参数集合逐项绑定 ① 源 span/逐字片段、② 参数语义（剂量体积/计数/空间界限）、③ 单位与量纲类别、④ 所属动作对象；由**源侧校验器**校验（对应 `validate_repeat_source`），并被 action_completion 流**单独消费**用于参数核验；**禁止**转换为 `AtomicPredicate`、**禁止**变更判定节点。在该合同存在前，正确行为是维持守卫并把该情形以明确原因保留为未核（fail-closed），而不是放开。
**[建议] 过渡期最小可观测修正**：为“操作参数数字被守卫拦住”提供专属原因/文案（现有 `numeric_predicate_missing` 文案“数值原文缺少可核验的比较条件”会误导——源含义没有问题；多数字情形更只落到 `:1090` 的泛化 ValueError）。不改判定，只改诊断。
**[不确定/竞态风险]** 单数字+单方向词的操作句（如“观察30分钟以上”）会精确触发 `numeric_predicate_missing`，而 deconstructor 对这类失败存在 `continue_numeric_predicate` 修复通道（首轮已读：`protocol_control_deconstructor.py:10433-10467` 附近）。我未读该修复提示词，无法确认它是否会把“操作参数”推向伪造的患者结果比较。**有界问题 Q-R1。**

---

### 3. 需要的测试（正向 / 等价布局 / 反事实 / 缺失证据）

**[代码事实] 既有锚点**
- 正向（typed 比较）：`test_numeric_alignment_preserves_inclusive_and_negated_comparisons`（`test_protocol_control_candidate_alignment.py:1452-1478`，≥/≤ 同义与否定，方向错即拒）；`test_alignment_rejects_short_quote_wrong_direction_and_wrong_function`（`:1425-1442`）。
- typed 操作计数先例：`test_source_repeat_count_uses_its_contract_not_a_measurement_predicate`（`:394`）、`test_conditioned_repeat_uses_frozen_local_action_sources`（`:452`）。
- 时间/量词反例：`:1481-1498`（字面频次≠可执行时间政策）、`:1501-1526`（量词是源语义）、`:1308`（后续列保留但不采用）、`:1529`（具名访视≠相对日期窗）。

**[建议] 新增（按优先级）**
1. **等价布局（当前边界的固化）**：合成手术句的变体——数字只出现在 `atom.statement` / 只出现在 `evaluation.proposition` / 1 个 vs 3 个数 / “以内”有与无——**全部必须**返回不可完整（当前为 `CandidateNumericAlignmentError` 或 `:1089-1090` ValueError），断言不存在任何布局变体可意外放行。**并揭示一个不对称**：方向/数字词表只看 `quoted_text`，经 `scope_quote`/表格标题进入的数字不在 `numbers` 内（`:1026`），需要专门用例断言该通道同样不能被用来夹带参数或阈值（我未追踪 scope 数字的其它约束，列为不确定）。
2. **反事实（决定性）**：“检查结果须低于40 U/L”，`decision_functions=["action"]`、`observation_policy.mode="action_completion"`、proposition 与 atom 文本逐字复制、核对答复 `fully_expressed` → 必须拒绝；并加**结构断言**：给该原子强加 predicate 会先被 `control_evaluation_spec` 的自校验拒绝（mode⇔operation⇔predicate 与 action_completion 约束），证明“标签+模式+抄写”无法绕过。
3. **下游负向对照**：构造一个参数化 action_completion 配对与“已完成”见证，证明 `select_qualified_relations` 只核完成+范围、**不核参数**（`:105-116`）——用于说明守卫为何必须保留，任何放开都必须先有参数消费者。
4. **缺失证据（现状）**：保持守卫时，参数化原句应产出“未核/不采用”，不得转成受限“来源歧义”，也不得触发完整采用；若未来加入参数合同，则新增：每个参数缺 span/单位/动作绑定即拒（对应 `validate_repeat_source` 的失败系）。
5. **反“模型一致”**：同一反事实但把核对答复、`decision_functions`、policy 全部设为“正确”形态——仍必须拒绝（即 1/2 的合并用例）。

---

### 4. 作用域与阶段风险（仅机制，不做临床判断）

**[代码事实] 既有阶段/作用域约束**
- `control_scope_sources.py:105-117`：标题引用**只提供时期作用域**，必须与该要求的冻结祖先引用完全一致，且不得顶替来源单元；`:74-102` 祖先标题需唯一物理位置（不得用正文 span 代替）。
- `qualified_proposition_evidence.py:11-28`：控制类配对的“当前节点”必须落在 `decide_at_node` 绑定的映射中，否则 `proposition_current_node_unverified/mismatch` 拒绝。
- 对齐提示 `candidate_alignment.py:592`（native 指令）：`at_or_before_baseline` 不得遗漏；`after_baseline` 保留但不要求成为当前候选动作；`:941-955` 完整判定还要求候选节点含对应标题物理来源（`validate_scope_citations` + `resolve_ancestor_scope_citation`）。

**[建议/风险]**
1. **“源链接到基线目标”不是时机证明**：那是作用域来源关系（标题/单元），不是执行节点。任何未来的参数合同必须绑定**冻结判定节点**（`review_node_bindings` 的 `decide_at_node`）与既有时间消费者（`time_constraint`/`time_purpose`、`_ANCHOR_WORDS` `:141-144`），**不得**因“链接到基线”而把给药后操作编译成给药前入组前提。参数只描述“操作怎么做”，不描述“何时算达标”。
2. **参数合同不得兼职时间/次数**：`RepeatScheme` 与 `time_constraint` 已有独立消费者；把“6 个区域/3 mL”塞进任一条是类型混用，会导致时间/次数语义被静默替换。
3. 测试面：现有 `:1308`（后续列保留不采用）、`:1529`（具名访视≠相对日期窗）应纳入参数能力的回归矩阵，防止阶段语义被参数改动波及。

---

### 优先缺陷/替代与决定性不确定

**缺陷/替代（按影响）**
- **D1（能力缺口，最高）**：操作参数无类型化消费者；守卫因而成为唯一屏障，同时造成漏判家族。替代：新增最小“操作参数”类型合同（§2），**不是**放宽守卫。**限制**：这是产品能力决策，非本审阅可批准；在合同落地前，维持 fail-closed。
- **D2（诊断误导，中）**：`numeric_predicate_missing` 文案与多数字泛化 ValueError（`:52-53、1090`）会让“参数完整”错报为“比较条件缺失”。替代：专属原因码/文案（零判定改动）。**限制**：只提升可观测性。
- **D3（词表完整性，中）**：`_COMPARISON_WORDS` 不含“以内/范围内/正常范围”，使得任何“以方向词判断是否有阈值”的放松都是不安全的。替代：如果未来做类型化，必须由类型合同承担，而不是补词表。
- **D4（修复通道不确定，中）**：单数字+单方向词的操作句会进入 `continue_numeric_predicate` 修复通道。**有界问题 Q-R1**：该通道是否会把操作参数推向伪造的患者值比较？（我未读提示词，不宣称。）
- **D5（布局不对称，低-中）**：数字仅在 `scope_quote`/表头时不被 `numbers` 扫描（`:1026`）；需专门用例确认无夹带通道（未追踪其它约束，列为不确定）。

**决定性不确定**：真实 deep_0049 的停止原因是否为该守卫（主机说停在 `SOURCE_CANDIDATE_SEMANTICS_UNVERIFIED`，而守卫是**对齐失败**而非 SCR 语义负——两者的错误类不同）。若真实停止不是本守卫，则本评审结论仍成立但优先级需重排；**有界问题 Q-R2**：deep_0049 的对齐失败列表里是否含 `numeric_predicate_missing`（或 `:1090` 的泛化消息）？

**独立性折减**：审阅者与产品同族（仅适配器/上下文不同）；以上为源码合同级分析，不构成医学批准，也不能替代完整 1006V1 流程；未读临床原件，未对实际材料作任何诊断或建议。

**证据清单**：`control_evaluation_spec.py:13-44、57-104、107-163`；`candidate_alignment.py:20-53、120-165、417-545、895-1114`；`proposition_evidence.py:60-182`；`qualified_proposition_evidence.py:1-28、71-138`；`control_scope_sources.py:74-117`；测试 `test_protocol_control_candidate_alignment.py:1-68、1425-1526`（另据首轮：`deconstructor.py:10433-10501`、`:10514-10565`）。限制：未取得 git diff（Bash 不可用），定义均按符号锚定直读；未读 `AtomicPredicate` 与 numeric 修复提示词的完整定义。
