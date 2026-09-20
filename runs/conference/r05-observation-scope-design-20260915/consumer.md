# 会议输出: r05-observation-scope-design-20260915 - evidence_single_object

## Output

同会话续审完成。只读；未改文件、未运行任何测试/模型/库/浏览器、未派发。本轮覆盖：(A) 所有者已实现的 S4 源码逐函数审阅，(B) 对拟议 `assertion_extent`（S1 下一最小段）的挑战与最小修订，(C) S2/S3 边界确认。S4 为**已改源码**的审阅结论；S1 为**设计建议**，未实现、未采信。

### A. S4 已实现源码审阅

#### A1. 实现核对（证据，与所有者描述一致）

- 未决配对携带原 fact/locator：`app/services/qualified_proposition_evidence.py:74-78`（`select_qualified_relations` 的 unresolved 项取自 `evidence["pairs"]` 的 `fact_id`/`locator_id`）；`PROPOSITION_CONSUMER_VERSION` 升 v3（`:6`）。
- 未选关系的原位置保存：`app/services/qualified_binding_selection.py:538-548`（`identity_selection_unresolved` 项带 `fact_id` 与经 `verified["pairs"]` 解析的 `locator_id`）。
- `PropositionPairGap` 合同与校验：`app/projections/control_calculation_experiment.py:25-30`（pair/identity/fact/locator/reasons），`:196-206` 核 identity 在选择清单、fact 属冻结事实、**locator 属该事实的 `locator_ids`**（字段依据 `app/domain/contracts/facts.py:256`）、pair 级不与已选关系重叠且不重复（`:203`，同 fact 不同 pair 合法，符合所有者裁决）。
- 仅原结论 UNKNOWN 时合并：`:273-285`——`truth == UNKNOWN` 才并入 gap 原因；同时新增 `observation_scope_partially_covered`（部分覆盖检测扫已选关系的 lanes，`:276-281`），S4 顺带落实了我上轮 D2 的最小消费。
- 报告带疑问位置不写 used_fact_ids：`app/projections/control_review_outcome.py:62-63,79-80`（gap locator 并入 `locator_ids`，`used_fact_ids` 仅取 operands）。
- 版本纪律：consumer v3 / selection-consumer v9（`app/domain/contracts/qualified_binding_selection.py:23`）/ experiment v9（Literal、默认值与 `selection_payload` 三处一致，`control_calculation_experiment.py:34,291,296`）/ evaluator v13（`app/services/frozen_review_calculation.py:27`）；material v3 门控命题字段、旧版本不得补入（`qualified_binding_selection.py:166-196`）；`_validate_authorization` 比对 v9 消费算法，旧授权自然失效。接线：`frozen_review_calculation.py:192-201` 将 `material.unresolved_proposition_pairs` 传入计算。均符合"旧批准不继承"。

#### A2. 决定性源码问题 R1：gap 定位与正式保存校验冲突（会在启用时阻断主场景）

`app/storage/review_control_repository.py:100-102` 要求 `item.locator_ids ⊆ used_fact_ids 所引事实的 locator_ids`。而 gap 定位按设计**不**写入 `used_fact_ids`（`control_review_outcome.py:79-80`）。推演两种可达场景：

- **场景一（S4 的主场景，失败）**：某配对因双路 relation 分歧或来源资格不合格成为 gap，其 fact 从未进入已选关系 → 无 operands → fact 不在 `used_fact_ids` → gap locator 不在 allowed 集合 → 正式保存整个控制结果批次时抛 `补充要求的原件定位不属于所引用事实`。即 S4 最需要呈现的"未决配对"恰恰使正式链无法保存。
- **场景二（所有者声明的合法场景，通过）**：同 fact 两 pair，一条已核实（fact 被选用）、一条未决 → gap locator 恰属已用 fact，校验通过。

即现有校验只放行巧合子集，阻断常态主场景。连锁的第二处误指风险：`app/services/control_action_publication.py:53` 用 `next(iter(obligation.locator_ids), None)` 取**排序后第一个** locator 作为行动触发定位——gap locator 并入同一列表后，行动可能把用户指向疑问位置而非真实依据位置。

**最小修复建议（二选一，推荐 b）**：
- (a) 仓库校验扩展 allowed_locators 至"上下文全部事实的 locator"——改动最小，但把"已用"与"存疑"两类定位继续混在同一字段，不解决 A3-3 的角色混淆；
- (b) `ControlObligationOutcome` 增设独立字段（如 `doubt_locator_ids` + `doubt_reason_codes`，默认空列表，旧载荷可读），`control_review_outcome.py` 改为分别填充；仓库对两组各按各的事实基础校验（doubt 组对 context 全部事实）；`control_action_publication.py:53` 改只取已用定位，`review_history_service.py:571` 的并集改为显式合并两组或分开呈现。该链尚未启用、无历史持久行，版本内扩字段成本最低；若按项目惯例升 `control-review-outcome/v2` 亦可，二选一由所有者定。

#### A3. 次要发现（建议级）

1. `qualified_binding_selection.py:541` 裸 `next(...)` 无默认值：若不变量被破坏抛 StopIteration 而非可诊断错误。建议 `next(..., None)` + 显式 `InvalidJobDefinitionError`。
2. gap 校验未限定 `determination_mode ∈ {semantic, investigator_judgment}`：生产端只产生语义类 gap，但消费端手工路径可给确定性原子塞 gap 并在 UNKNOWN 时并入原因。建议加对称校验，与关系路径一致。
3. 原子已决（TRUE/FALSE）时，其兄弟 gap 的 locator 仍进 `locator_ids` 但原因不进任何输出字段（`observation_reason_codes` 只含 observation 原因与 unresolved），报告读者看到"无解释的定位"。修复 b 的 `doubt_reason_codes` 顺带解决。
4. gap 原因按 identity 整体并入（`control_calculation_experiment.py:274-275`），不区分该 gap 的 fact 观测是否已 TRUE/FALSE——偏可见性、无误判，接受；仅记录。

### B. S1 设计挑战：`assertion_extent` 是否足够

#### B1. 充分性判定（推断 + 论证）

`(relation, extent, mode)` 三元组**可以**组成完备的量词语义，但仅成立于两个前提：

- **前提一：命题是单例形，量词只来自 mode。** 现有解构提示已是此形（"这些模式表达本原子proposition"，`app/agents/protocol_control_deconstructor.py:1241-1242`）。若解构产出范围级命题（如"受试者无任何X"配 mode=any），relation 已在评价全称命题，extent 变成冗余且互相干扰。需在提示/校验层固定：relation 永远按单例命题评判；extent 描述**记录断言的辖域**，绝不重定义命题。
- **前提二：extent 必须进入 `agreement_key`。** 现有 key 含 scope_correspondence（`app/domain/contracts/proposition_evidence.py:47-50`）；若 extent 不进 key，一路判 entire、一路判 individual 而关系一致时会以 `*_agreed` 通过——恰好绕过双读要防的分歧。这是拟议条件清单（"两路一致"仅明确覆盖 scope_quote/relation）中的**必要补充**。

组合表（聚合只需新增两格，与"反方向只在…"一致）：

| mode | relation | extent | 结论 |
|---|---|---|---|
| any | entails | individual | TRUE（既有单向见证） |
| all | contradicts | individual | FALSE（既有反例） |
| all | entails | entire | **TRUE（新增）** |
| any | contradicts | entire | **FALSE（新增）** |
| any | entails / all | contradicts | entire | 无需 extent，单例见证已覆盖；建议不允许 extent 产生前向结论，保持改动最小 |

#### B2. 残余歧义（回答所有者问题：是，仍有两类，需条件而非新字段压制）

1. **否定辖域漂移（即"对任一事件的否定"被当"所有事件均不存在"的真实机制）**：危险方向是**假阳性 entire**——记录*提及*整个范围但*断言*只落在单例。例："既往多次复查，本次未见X"（范围词在场，scope_correspondence 可判 supported，但断言辖域是"本次"）；"目前无X"（时间限定收缩全称域）。若判成 entire，ANY-FALSE 错误成立——比 UNKNOWN 更糟。须在提示中把 extent 与 scope_correspondence 定义为**两个正交轴**（对应=文本与范围的关系；extent=断言的量词辖域），并规定 entire 的引文必须同时显示：①对 scope 整体的穷尽表述（"任何/全部/所有…均…"或等价），②该穷尽作用于（肯定或否定）单例命题，③**无收缩辖域的限定词**（"目前/本访视/本标本/自述"等）——任一不满足填 individual 或 unresolved。
2. **报告者权威漂移**：患者自述否认/勾选项的"穷尽"是报告者知识域，不是临床档案域；医生整编病史总结才是目标证据。不必新增字段：提示规定自述/据述类否认不构成 entire（除非原文显示经核实的整体总结），并把两类文本放入评测负例集。

#### B3. 最小修订清单（不含无期限保持 UNKNOWN 的替代）

1. 合同：`PropositionEvidenceCheck` 增 `assertion_extent: individual|entire_declared_scope|unresolved`；`PROPOSITION_EVIDENCE_VERSION` v3→v4，旧记录不补字段。
2. 校验器：entire ⇔（scope_correspondence == "supported" ∧ scope_quote 非空 ∧ relation ≠ undetermined ∧ observation_policy 存在）；partial/unresolved/无范围/关系未定 ⇒ extent ∈ {individual, unresolved}；`agreement_key` 加入 extent。
3. 提示（同一次双读，`app/llm/proposition_evidence.py` system 段增约四句）：两轴正交定义、entire 三条件、限定词/自述降级、entire 不改变 relation 也不被 relation 推导。
4. 聚合护栏（在所有者条件清单上补两条）：前向决胜见证优先于 entire 反向结论；两者方向相反时保留决胜结果并附加非阻断原因 `entire_statement_contradicted_by_witness`（不丢矛盾信息）。其余条件（非确定性 any/all、无该 identity 任何未决配对/UNKNOWN/来源冲突、所有合格内容配对均在核实关系中、无方向矛盾、两路资格与日期合格）经推演均健全，且各锚点已有实现位（identity_coverage、gaps、selected_conflicts、时间机器）。
5. 命名：若尚未实现，建议 `universal_over_declared_scope`（断言量词义）优于 `entire_declared_scope`（易被读成"记录覆盖度"，与 scope_correspondence 混淆）；改名成本为零时优先。
6. 评测负例集（最终统一评测）：范围词在场+单例断言、"目前/自述"限定、双路 extent 分歧、entire+前向反例并存、空成员集下的全称肯定。不改任何既有单向见证行为。

不新增模型请求/任务：extent 由现有 proposition 双读顺带产出，聚合为确定性代码；符合"不再造孤立候选任务"。

### C. S2/S3 边界确认

- S2 逐成员原子 + 仅有限 AND 枚举才拆、OR/例外分支保留：同意，与我上轮方案一致且约束更准确（"或"枚举拆成 ALL 组会反转语义，必须禁止）。评测需含"一句话枚举三项检查拆三原子"与"'或'枚举不得入 ALL 组"两例。
- S3 三分（最近实际发生日期=date_range、报告日期=record_time、原文明确复查取代）与现有 `time_operand_attribute: Literal["date_range","record_time"]`（`control_evaluation_spec.py:48`）对齐，本段不实施正确；实施时需保留被替代观察供审计、部分日期不可比/并列时显式 unresolved、不默认 latest。

### D. 决策点与有界问题

- **Q1（阻断级）**：R1 修复选 (a) 扩仓库校验还是 (b) 独立 doubt 字段？我推荐 (b)，并同步修 `control_action_publication.py:53` 的首定位取值；请所有者裁决，否则 S4 链在首次正式保存含常规 gap 的结果时即被自身校验拒绝。
- **Q2**：B3-5 命名（`universal_over_declared_scope`）是否采纳——实现前改名零成本，实现后即成版本负担。
- **Q3**：entire 是否同样禁止用于 investigator_judgment 命题（书面判断的"整范围总结"是否可能合法存在，如"研究者确认全部病史已核无遗漏"）？我倾向允许但要求 investigator_attribution=supported，请裁决。

### E. 不确定性声明

以上为源码级审阅与设计论证；S4 链构建后仍未启用、无评测与采信授权；R1 的触发推演基于对生产者-消费者不变量的静态追踪，未运行验证。S1 全部为设计建议，未实现。本报告不构成临床、监管、视觉或最终采信结论。
