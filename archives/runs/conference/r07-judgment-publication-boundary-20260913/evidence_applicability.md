I'll inspect the actual deconstructor prompt, schema, and the three consumers, then pin the applicability boundary to explicit fields rather than names.# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读。本轮只钉适用性边界：谁该进书面判断检索/P2，谁只是专业评估记录。不改临床布尔、不刷新夹具、不跑套件。

### Evidence

**上游两个解构器对同一布尔的语义不是一回事。**

入排解构（`protocol_deconstructor.py`）：

- 系统合同要求保留「研究者判断」为原子条件（244–250、352–353），**没有**定义 `requires_professional_judgment=true` 的三态。
- compact wire 合同（373–406）不解释该布尔。
- Schema 仅要求原子带布尔（569、626）；wire 原样拷贝（1857–1915）。
- `EvidenceRequirement` 的 `required_source_types` 是自由字符串数组，无枚举（706–730）；装配时从模型输出拷贝（2602–2621），**不会**因原子布尔自动写入 `investigator_assessment`。
- 门控 `INVESTIGATOR_JUDGMENT_DROPPED`（`deconstruction_gate.py:1686-1700`）只在组件原文匹配 `_source_requires_investigator_judgment`（395–411：研究者 + 评估/评定/判断/判定/认为/认定/确定/决定/确认/同意）且**没有任何**原子布尔为 true 时报警。诊断、评分原文不匹配该模式时，门控不要求该布尔。

跨章控制解构（`protocol_control_deconstructor.py:1360-1364`）才有操作定义：

> `requires_professional_judgment` 仅在该原子本身需要研究者、医生或其他专业人员作判断时设为 true；患者自填/自评、机械计分、范围核对或资料是否存在不得仅因需要审核就设为 true；**医生评分、研究者临床判断等原文明示或工具固有的专业评估保持 true**。

同文件 1532–1536：`SELF_REPORTED_TOOL_RESEARCHER_EVIDENCE` 把「研究者评估记录」列为最低证据，**仅当存在独立研究者判断义务**。最低证据 `required_source_types` 与原子布尔是两条平行模型输出（621–627、2453–2459），互不由代码推导。

因此控制提示已把 **(b) 医生评分/固有专业评估** 和 **(c) 独立研究者判断义务** 都标成同一原子布尔；只有最低证据那条把 `investigator_assessment` 留给 (c)。入排解构连这点都没写进提示。

**已发布关系（`rules.py:183-198, 279-289`）：**

| 对象 | 有 | 无 |
|---|---|---|
| `AtomicPredicate` | `predicate_id`、`requires_professional_judgment`、`subject`/`attribute`、原文定位 | 书面判断 vs 已记录专业评估；`requirement_id` |
| `EvidenceRequirement` | `requirement_id`、`fact_type`、`required_source_types`、`due_stage`、`description` | `predicate_ids`；书面判断标志 |

`fact_type` 相等不是归属证明（§17.2 已写）。EX-01 袋要求 `laboratory_and_investigator_risk` 对六个谓词零命中，仍是现存合成形状。

**三个消费者：**

- 检索选择 `select_judgment_search_requirements`（`judgment_search_job_service.py:84-116`）：到期模板的 source types 含 `investigator_assessment`，**否则**若组件 `determine_component_mode == INVESTIGATOR_JUDGMENT` 仍选中该**整条**要求。
- `determine_component_mode`（`clause_pack.py:50-61`）：组件内**任一**原子布尔 true → 整组件 `investigator_judgment`。页审 ClausePack 用同一派生（124）。
- 现场 `_requires_investigator_judgment`（`eligibility_review_projection.py:386-394`）：组件 mode **或** 该要求 source type。`_summary_gaps`（427-431）对组件内**每条**到期要求套这个或。合成 EX-02 仅 `screening_record` 也会因 mode 被当成书面判断。
- 期望缺口 `expectation_gap_signals`（`fact_expectation_gaps.py:245-247`）：**只**认 `investigator_assessment`。v2 投影同样：检验事实不能覆盖书面判断要求（`evidence_expectations.py:148-150, 294-302`）。

检索/现场用组件 mode，期望生成不用。组件 mode 来自「任一专业评估原子」，不是「本条要求要书面判断」。

**求值器**（`expression.py:460-466`）：无匹配事实且原子布尔 true → `professional_judgment_unverified`（未核实），不是缺失。

### Inference

现在**够用、且已是要求级发布字段**的关系只有：

`EvidenceRequirement.required_source_types` 含 `investigator_assessment`。

它是要求级、已进模板/期望哈希、控制提示已把它限制为「独立研究者判断义务的个例证据」，v2 覆盖已禁止用检验结果顶替。书面判断检索、P2、缺文件互斥都应只认这个键。

**不够、且会误标的关系：**

- 组件 `determination_mode` / 任一 `requires_professional_judgment`：把诊断、医生评分、过敏史等专业评估组件的**客观测量要求**一并送进检索和 `_summary_gaps`。
- `fact_type` 字符串：不能证明谓词归属。
- 入排原子布尔：提示未定义，历史值可能是「模型要懂语义」「记录里已有专业评估」或「要另写判断」。

缺的是版本化、默认为空的细分，而不是再派生一套组件分类：

1. 原子上区分「记录即专业评估」vs「方案要求针对对象另作书面判断」。
2. 要求到谓词的显式列表（有才填；空=未证明，失败闭合）。

未再发布前，把历史布尔或组件 mode 当成书面判断，就是在改临床含义。

### Recommendation

**现在可做的有界切片（不改已发布规则、不改 `determine_component_mode` 定义、不重算 ClausePack）：**

1. `select_judgment_search_requirements`：删掉 107–114 的 mode 回退。只选 `investigator_assessment ∈ required_source_types` 且当前到期的 `requirement_id`。无此类要求 → 现有「没有需要检索…」错误，不要降级去搜整个专业评估组件。
2. `_requires_investigator_judgment`：只读该要求（或模板）的 `required_source_types`，**不要**读 `component.determination_mode`。`_summary_gaps` 与 `_reason()` 随之变成要求级；测量兄弟要求不再被整组件刷成 PJ/OU。
3. `expectation_gap_signals` 保持现状（已是 source type）。四态对齐：未检索/失败/范围不合 → OU；候选未核实 → OU；双读供给域零候选且无同要求缺文件 → PJ；核实后的书面判断事实按 v2 覆盖解除 PJ。现场不要再用摘要二次 `update` 盖过同要求缺文件（缺文件跳过已在 `_summary_gaps:417-418`）。
4. 求值器布尔 → `professional_judgment_unverified` 保留。已有诊断/评分事实且该要求**未**列 `investigator_assessment`：走普通覆盖，**不**开检索、**不**发「请补写判断」。
5. 正式发布仍只消费要求级 v2/`RequirementGapState`；不把 v1 `ABSENT` 放宽为 PJ。本切片不刷新四份冻结夹具。

页审 ClausePack 的 `investigator_judgment` 仍表示「VLM 不要对确定性阈值下方向」。不要用它选检索目标。

**未来新 RuleSet revision（追加字段，旧 JSON 缺省=未声明，不改写旧行/旧哈希）：**

| 位置 | 字段 | 缺省 | 派生 |
|---|---|---|---|
| `AtomicPredicate` | `professional_evidence_role`: `recorded_professional_assessment` \| `explicit_written_investigator_judgment` \| 省略 | 省略 | 新解构输出。书面判断：原文符合门控已用的「研究者+判断动词」（`deconstruction_gate.py:395-411`），由模型填写、门控核对，**禁止**用该正则回写已发布布尔。记录型专业评估：医生评分/诊断等「记录本身即评估」（控制提示 1362–1363）。`none` 不必单列，省略即可。 |
| 保留 | `requires_professional_judgment` | 冻结历史 | 新稿：书面判断或记录型评估均可仍为 true，供求值器未核实；**检索/P2 不读它**。 |
| `EvidenceRequirement` | `written_judgment_predicate_ids: list[str]` | `[]`，序列化可省略 | 仅当该要求 `required_source_types` 含 `investigator_assessment` 且能指出组件内对应书面判断谓词。空列表=未证明归属，失败闭合，不靠 `fact_type`。 |
| 控制 `minimum_evidence.required_source_types` | 继续只在独立书面判断义务时列 `investigator_assessment` | 已有提示 1532–1536 | 入排解构补同一句：原子布尔 true **不等于** 资料类型含 `investigator_assessment`。 |

新 revision 发布后，检索/P2 仍只认 source type（可再用非空 `written_judgment_predicate_ids` 抑制**那些**谓词的 unverified）。旧 revision 永远走「仅 source type；布尔只产生未核实」。

**已发布含混要求、不再发布时的安全行为：** 必要。没有 `investigator_assessment` 的历史要求：即使原子布尔 true、组件 mode 为 investigator_judgment，也保持 **OU/普通资料缺口**，不检索、不报缺失、不要求对已有诊断再写一份声明。有该资料类型的要求：维持现 P2。不得按病名/条款号补丁。

**真语义证明仍挡住的：** 给旧规则回填 `professional_evidence_role` 或 `written_judgment_predicate_ids`；用 `fact_type` 当谓词证明；把诊断事实自动当成 `investigator_assessment` 要求的满足；改 `determine_component_mode` 以致旧 ClausePack 哈希变化。用户授权的是开发接线，不是改方案临床含义或未评测绑定。

### Uncertainty

未打开生产库核那 15 条「结构选中、资料类型未标」的要求原文。PROJECT_CONTEXT 已声明不能证明它们都需要另写判断；本切片按「未标 `investigator_assessment` = 不检索」处理，与该声明一致。入排模型实际如何填该布尔，提示未定义，只能当含混历史。未跑测试。
