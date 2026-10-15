# 会议参与者输出：enrollment-protocol-gate-review-20260908 - general_single_object

## 边界检查

- 在运行器绑定的工作区内工作（`phase5-clinical-facts-profile` 工作树）。仅读取声明的源集：冻结运行 `artifacts/phase55-model-comparison/20260907/protocol-native-runs/d001-glm-low-v1`（manifest, execute_record, SQLite in `mode=ro`, receipts/histories），权威 DOCX（仅通过 python-docx 读取），以及 `app/protocols/deconstruction_gate.py`，`app/agents/protocol_deconstructor.py`, `app/agents/protocol_semantic_model_router.py`, `app/agents/protocol_semantic_transport.py` 及其导入的合约。
- 未进行任何写入操作：所有诊断均为进程内只读（SQLite `mode=ro`，磁盘上无临时文件，无服务变更）。无模型/OCR/API 调用。无规则发布，无临床决策。未读取其他参与者的输出、负责人对比结果或患者数据。
- 我在进程内执行了实际的 gate 辅助函数在冻结数据上以确认触发机制（离线只读诊断，明确允许）。这不是模型调用，也不是记录变更。
- 保留最后验收意见：Codex 保留最终的临床、监管和发布决定权。分配的模型/努力（GLM-5.3-Flash, max）在会话内未更改。

## 独立工作成果

### 1. 总体结论

冻结的 D001 GLM-low 运行在约 33 分钟内进行了 63 次模型调用，没有接受任何批次，并产生了一个草稿，其自身的 gate 拒绝了该草稿，并列出了 31 个阻塞性问题（7 个布尔值，17 个时间，7 个来源覆盖；gate 版本 `protocol-deconstruction-gate/2026-09-02.2`，位于 `job_checkpoints` 步骤 `integrity_check` 中）。我在源 DOCX、结构化草稿和 gate 实现的基础上，独立验证了会议所选的三个条款以及两个额外的条款。结果：**至少有两个针对性检查被证明是校验器误报，且其中一个被构建为在没有破坏来源忠实度或临床语义的情况下无法满足**。这——而不是模型质量——是导致 1000 万 token 修复循环没有收敛的主要原因。

### 2. 各条款分类（观察结果 + 推理，均已验证）

| 条款 / 问题代码 | 分类 | 依据 |
|---|---|---|
| IN-06 `DISJUNCTION_CHANGED_TO_CONJUNCTION` | **误报 (FALSE POSITIVE)（经验证）** | 见 §3 机制 A。草稿在两个真正并发的义务上使用 `all`；每一个源“或”要么处于否定作用域内（无怀孕**或**捐精计划 = 均无计划），要么是修饰语级别的析取（高效**或**可接受）。DOCX IN-06（研究人群/入选标准 第6条）："有生育能力的参与者自签署知情同意书至研究末次给药后至少3个月无怀孕或捐精计划，必须遵守避孕的相关规定…"。拆分为 ANY 分支（修复指令所要求的）将改变资格逻辑：ANY 之下的 无A或B 意味着 NOT(A AND B)，这会错误地接纳一个有怀孕计划但没有捐赠计划的受试者。 |
| IN-06 `PROSPECTIVE_WINDOW_NOT_STRUCTURED` + `PROSPECTIVE_PERIOD_NOT_IN_SOURCE` | **真实模型错误（TRUE model errors）** | 源具有明确的前瞻性窗口 "自签署知情同意书至研究末次给药后至少3个月"；草稿将 `prospective_period: study_period`（源中无此枚举）并将 `prospective_window: null`。Gate（deconstruction_gate.py:2273-2336）正确地要求对 末次给药 + 3个月 进行锚定+界限结构化。模型构建不足，可修复。 |
| EX-02 `PARENT_RULE_OBLIGATION_NOT_COVERED` (未承接：筛选或基线时) | **合同下为真（TRUE under contract），存在设计冲突** — 见 §3 机制 C | 经验证：`_substantive_obligation_segments` 将父级拆分为 ["筛选或基线时", "存在其它皮肤病…", "经研究者判断…"]; 谓词绑定了段落 2 和 3，但未绑定 1（与谓词的 `attribute` 共同运行 = 1 < 2，尽管整个句子在 `source_clause` 中被逐字引用）。模型可以通过将 阶段限定词 放入 `source_term`/`attribute` 来满足此要求 — 因此这是一个真实的解构差距，而不是损坏的检查器。但参见 §4 风险 3：相同的 token 被布尔族称为“审核节点”。 |
| EX-08 `LOCAL_EXCEPTION_MAY_WAIVE_CONCURRENT_TRIGGER` (+ EX-24 相同) | **真阳性 (TRUE positive)** | 源 中的括号仅限于真菌感染项目；草稿将其提升到了组件级别的 `exception_expression`（指甲浅表真菌感染）。在该系统的组件级异常语义下，一个患有甲真菌病且同时患有复发性尿路感染（研究者认为有风险）的受试者会被错误地豁免。真正的不安全结构；正确的修复方法是采用具有分支局部异常的独立触发组件，或者不进行组件级提升（完整的括号已经存在于主谓词的 `attribute` 中）。EX-24（肠切除术（阑尾切除术除外），DOCX para 519）重复了相同的模式。 |
| EX-14 `INVESTIGATOR_JUDGMENT_DROPPED` | **由范围泄露触发；残留的临床判断待定** — 见 §3 机制 B | 经验证：组件 `component:EX-14:01` 和 `:02` 都带有完整的父句子作为它们的摘录；判断检测在完整摘录上匹配到了“研究者认为”，但**仅在组件 a 自身的片段上则没有**。“并列条件含研究者判断”的说法对于分支 a 的自身文本是错误的。残留问题："患有**或疑似**…" 部分是临床判断，因此 `requires_professional_judgment: true` 是可以辩护的 — 修复是安全的，但触发原因报告有误。 |

交叉检查条款（在范围内，反挑选）：EX-15 `DISJUNCTION_CHANGED_TO_CONJUNCTION` 是 IN-06 的另一个实例（经验证：仅间隙文本为 "，"，没有“或”；草稿在 [精神疾病, 影响] 上的 ALL 是可以辩护的，其中真正的“或”作为行内保留，RPJ 正确为 true）。EX-18a/g `DISJUNCTION_NOT_BOUND_TO_SOURCE` 是**真阳性**：ANY 结构与源匹配，但分支到源的逐字绑定确实不完整（得到 `PREDICATE_CLAUSE_NOT_IN_SOURCE` + `SHARED_TIME_QUALIFIER_NOT_BOUND` 家族的确证）。

### 3. 机制发现（信息价值最高的缺陷）

**机制 A — `_branches_have_source_disjunction` 计算包含在分支自身文本中的“或”。** `app/protocols/deconstruction_gate.py:467-504`。对于同级分支，它在 `between = compact_source[start:end]`（第 495 行）中搜索析取连接词，其中 `start` 是第一个分支锚点的开始，`end` 是最后一个分支锚点的结束 — 即整个联合跨度，**包括两个分支的锚定子句**。`_branch_source_anchors`（第 437 行起）锚定整个 `exact_source_clauses`，因此锚定子句内部的任何“或”（否定作用域下、修饰语级别或同义词对）都会被算作分支间的证据。在冻结草稿上运行：IN-06 的联合跨度包含“或”（在 无怀孕**或**捐精计划 内部），而间隙仅测试（"，必须"）则不包含 — 这就是满足 `has_or=True, has_and=False, ALL-top-level`（第 1573-1591 行）并在语义忠实、不可修复的草稿上触发 `DISJUNCTION_CHANGED_TO_CONJUNCTION` 的全部原因。EX-15 同样如此。
*最小通用修复：* 对于每对相邻锚点，仅在前一个锚点的结束和下一个锚点的开始之间的间隙中搜索连接词（或者在采用候选路径后，限制在第一个分支锚点结束之后）。回归期望：IN-06/EX-15 停止触发；真正拆分的草稿（"A，或B"，其中“或”位于分支文本之间）保持触发；EX-14 风格的“者，或研究者”保持触发（“或”位于间隙中）。

**机制 B — 研究者判断检测未限定在组件的自身分支上。** `deconstruction_gate.py:1673-1688` 针对组件摘录文本（`_component_text`，第 208-237 行）运行 `_source_requires_investigator_judgment`（第 395-412 行）。由于模型将整个父句子作为两个 EX-14 组件的摘录，分支 b 的“研究者认为”触发了分支 a 的标志。经验证：完整摘录 → True；分支 a 自身片段 → False。
*最小通用修复：* 使用基于组件谓词实际绑定内容所选择的片段，对摘录进行 `_substantive_obligation_segments` 切分，并要求判断短语在被认为未覆盖的组件所绑定的片段内。回归期望：EX-14:01 停止触发（或仅因“疑似”合理原因触发），EX-14:02 保持不触发（RPJ=true），EX-02 的真实判断谓词保持覆盖。

**机制 C — 复合阶段限定词落入实质义务分割器（splitter）和谓词绑定器（binder）之间的裂缝中。** `stage_only`（第 728-731 行）仅匹配单个阶段 token，因此“筛选或基线时”在 `_substantive_obligation_segments` 中作为义务保留下来，而 `_predicate_binds_obligation`（第 774-811 行）随后要求它进入谓词的语义标识，而不仅仅是逐字 `source_clause`。这与布尔家族自身的理论相矛盾，即“‘筛选或基线’是审核节点”（第 1569 行的动作文本和第 493 行的排除），并与证据要求已经带有 `due_stage: screening` + `baseline` 的事实相矛盾。这是一个 Codex 设计决策，而不是一个可以盲修的 Bug：要么复合阶段限定词在谓词级别被豁免（扩大 `stage_only`），要么在谓词标识/评估节点字段中强制要求它们（当前行为）。修复路径不同，模型和未来的黄金集（goldsets）需要一条一致的规则。

### 4. 修复循环成本（审核目标）

通过 `execute/receipts/request|response|receipt-0000..0062` 测得（全部 63 次调用 `finish_reason=stop`，无传输重试，最大输出 token 未达到）：

- 总计：**10,162,014 prompt tokens** + 158,743 completion tokens，约 33 分钟实际时间 / 34.5 分钟累计模型耗时，单次方案解构，结果为：无可接受批次，不可发布，等待用户。
- 最后一批次会话（53 次调用）占用了 98.5% 的 token（10.02M）。传输是仅追加的（`protocol_semantic_transport.py:115-120`："每次修复都会发送完整的先前用户/助手交换记录"），因此单次调用提示词从 44,689 tokens 增长到 **360,294 tokens**；成本呈二次方增长，修复提示词每次都会重新注入整个对话记录加上剩余的问题（`protocol_deconstructor.py:4662`，"这是同一会话的第 N 次定向修正"）。
- **修复上限是规则数量，而不是进展：** `semantic_repair_limit = max(16, len(parent_rule_catalog)) = 36`（`protocol_deconstructor.py:4364, 4452-4459`）— 运行完全耗尽了上限，最后一次调用标记为第 37 次定向修正。
- **无进展尾部：** 在 temperature 0.1 下，响应内容以 SHA-256 重复了 10 次；调用 49–62 包含了 11 次逐字重复较早输出的调用（一组三重：调用 35/49/62），在约 330–350K tokens/调用下 — 约有 **~3.2M prompt tokens (~32%) 花费在产生字节级相同的输出上**。产品循环没有重复检测器；仅有轮次上限。
- **收敛在结构上是不可能的：** IN-06（和 EX-15）的标志要求逐字摘录（保持内部“或” → `has_or` 为 true）和满足语义的逻辑（ALL，而非 ANY）— `DISJUNCTION_CHANGED_TO_CONJUNCTION` 无法清除。每一轮针对 IN-06 的修复都是保证被浪费的预算。
- **batch-all 放大了损失：** 草稿 ID `…-phase_ii-in-batch-all` — 所有 36 条规则都在一个批次中，`accepted_batches: 0` 意味着来自卡住规则的 31 个问题不让 23 条完全干净的规则被保留。按规则（或按子批次）接受本可以在人工审查开始前保留约 64% 的规则，并将剩余问题缩小到 13 条规则。

## 证据与假设

**证据（观察结果，定位符）：**
- 冻结记录：`manifest.json`（协议 D001-02-002，显式 phase_ii，停止后 `generate_draft`）；`execute/execute_record.json`（结果 `waiting_user`/需要核对，`accepted_batches: 0`，路由细节 = 3 个问题）；`job_checkpoints.integrity_check`（gate v2026-09-02.2，31 个问题）；`protocol_draft_revisions` rev 1（36 条规则/66 个组件/156 个需求；条款负载在分析中逐字引用）。
- DOCX（sha256 `362443131f…`，源保持读取）：IN-06 = para 466, EX-02 = para 470, EX-08 = para 476, EX-14 = para 489 — 所有草稿 `source_text` 字符串都与 DOCX 逐字匹配。未因文件名日期使用错误而扣分；读取了 II 期部分。
- 代码：`deconstruction_gate.py` 行数如上引用；`protocol_deconstructor.py:4364/4452-4459/4641-4662`; `protocol_semantic_model_router.py:410-432`; `protocol_semantic_transport.py:115-120`。
- 经验验证：`_component_text`, `_has_unambiguous_disjunction`, `_branches_have_source_disjunction`, `_source_requires_investigator_judgment`, `_substantive_obligation_segments`, `_predicate_binds_obligation`, `_branch_source_anchors` 在冻结输入 + 冻结草稿上在进程内执行；输出在上文 §2/§3 中重现。这是非 LLM 的锚定证据。
- 预算：逐个调用列表来自所有 63 个请求/响应/回执文件（消息计数、prompt_chars、prompt/completion tokens）；重复检测通过响应内容 SHA-256 完成。

**假设与不确定性（与上述内容分开）：**
- *推断：* 组件级 `exception_expression` 在该系统的评估语义中免除了整个组件（EX-08/EX-24 的“真阳性”分类的基础）。我从检查器的问题文本和修复行动中读取了这一点；我没有执行运行时评估器来观察豁免行为。如果运行时将异常限制在其源片段，分类将改为误报。
- *判断：* EX-14a 的“疑似”可以说是值得 `requires_professional_judgment: true`，无论检查器泄露如何；修复是安全的事实并不能使触发原因正确。
- *限制：* 同族审核（GLM-5.3-Flash 审核 GLM-5.3-Flash 输出）如数据包中所述得到承认；通过确定性执行和 DOCX 文本锚定核心声明来缓解。
- EX-19b / EX-18 时间标志的条款编号是根据草稿的 `display_code`s 交叉检查的，而不是重新导出完整的目录编号；我仅声称上述四个验证条款的 DOCX 定位符。

## 风险、差距和验证需求

1. **不可满足的检查器标志保证在未来的运行中出现失控循环**（最高风险）。在修复机制 A 之前，任何源包含析取 token 的子句在处于否定作用域下或位于子句内部的任何草稿上，都会在 `DISJUNCTION_CHANGED_TO_CONJUNCTION` 上失败。验证需求：使用 IN-06/EX-15 固定装置作为 must-pass 用例和当前必须失败用例（例如，带有 ALL 而源为 "A，或B" 的草稿）进行回归运行 gate。
2. **修复循环没有进展熔断机制。** 单次运行浪费了约 32% 的 token 在相同的重复上，并以轮次上限而非收敛或升级告终。验证需求：一个单元测试，即 K（例如 2）次相同的（问题集，范围，替换 JSON 哈希）元组会停止循环，并将该规则路由到需要人工核对。
3. **检查器间的信号冲突 (筛选或基线)。** 布尔族：审核节点；source_coverage：必须绑定的实质性义务；证据要求：due_stage 已经携带了它。模型收到矛盾的指令；未来每个协议的黄金集（goldsets）将继承这种歧义。需要 Codex 做出决策（见问题）。
4. **路由审计细节掩盖了失败面。** `route_failure_detail` 仅保留最后尝试问题的前 `[:3]`（`protocol_semantic_model_router.py:426`），因此用户和本次会议看到的是 "IN-06/EX-08/EX-14a"，而草稿实际带有 31 个问题，涉及 13 条规则。最小修复：附加每个检查的计数（布尔值 7 / 时间 17 / 来源覆盖 7）和受影响规则列表。
5. **batch-all 接受丢弃了干净的工作。** 23 条规则通过了每一次检查，但因为 `accepted_batches: 0` 而无法发布。如果按规则保留，将改变此运行的经济性；需要产品决策，因为 AGENTS.md 边界（稍后阶段的证据不得静默重写早期结果）对于 *发布*（而非接受）仍然完好。
6. **同样的泄露机制可能存在于我未抽样的其他检测器中**（文本启发式作用于作为分支共享的摘录）。EX-08 家族和 EX-18 家族标记通过了语义审查，但针对组件自身片段的 `_source_supports_predicate_negation` / 数值/时间检测器的系统性审计将是低成本的保险。

## 推荐下一步

1. **Codex 应将机制 A 和 B 分类为必须修复的检查器缺陷**，并附带上述回归示例；两者都是小的、通用的、非临床的更改，它们消除了已证明不可满足的标志和错误归因的标志。提升 `DECONSTRUCTION_GATE_VERSION`（`deconstruction_gate.py:77`），根据其自身的注释规则更改判定语义。
2. **在修复循环中添加重复输出熔断器 + 按规则升级**（2 次相同的修复 → 停止，用问题列表升级到需要核对）；这仅在本次运行中就可以节省约 3M tokens，并且纯粹是机械性的。
3. **通过按规则接受（或子批次接受）来保留干净的规则**，等待 Codex 的产品决策；保留发布门控不变。
4. **按照 §4 风险 3 修复报告截断 (`[:3]`) 和阶段限定词策略决策。**

**Codex 的有限问题（同会话可回答）：**
1. 组件级 `exception_expression` 是否设计为在运行时评估中免除整个组件，还是仅作为审查指导？（这决定了 EX-08/EX-24 是“草稿中的真实语义错误”还是“标记错误描述了一种不可能的评估”。我的分类假设前者。）
2. 对于“筛选或基线时”，预期的语义归宿是什么：(a) 扩大 `stage_only` 以豁免复合阶段限定词，(b) 谓词标识/新的评估节点字段必须绑定它们，还是 (c) 当 `due_stage` 覆盖两者时接受 `source_clause` 逐字绑定作为覆盖？决定决定了 IN-06 风格的前瞻性窗口谓词和 EX-02 风格的审查节点谓词的未来黄金集。
3. 按规则接受草稿是否在本次阶段的产品合同范围内（接受 ≠ 发布），还是应该将其推迟到第 5 阶段之后？
4. 我的修复循环审计仅涵盖 `deepseek`/`zhipu` 主路径（`semantic_repair_limit=None` → 基于规则数量）— 非固定路由是否也会遇到相同的无进展尾部，即重复熔断器是否也应该是运行器路由审计的一部分？

**恢复点：** 所有证据都是从冻结的工件中以只读方式获取的；无需进一步工具即可重现上述每个声明（脚本逻辑已在线内包含在本报告中）。如果 Codex 对问题 1–2 的回答改变了我的 EX-08/EX-14 分类，仅需重新运行组件级异常语义的运行时评估器；其他一切均已锚定。
