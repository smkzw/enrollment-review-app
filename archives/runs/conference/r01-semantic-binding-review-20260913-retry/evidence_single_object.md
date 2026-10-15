全部证据已收集完毕。以下为完整审阅报告(按指派输出模式返回，不写运行目录文件)。

---

# Conference Output: r01-semantic-binding-review-20260913-retry - evidence_single_object

## Output

### 0. 审阅基线(证据)

- 六项源文件 SHA256 复核全部与 `R01_REVIEW_INPUT_20260913.md:51-56` 一致，按该版本审阅。
- 实跑 `tests/v2/test_predicate_semantic_binding_boundary.py` + `tests/v2/services/test_predicate_candidate_scope.py`:5 passed、2 strict xfail,与输入声明一致(确定性测试，未调用任何模型)。
- 补充实证(一次性脚本，仅构造 `EvaluationContext`,未写库未调模型)：模拟 `_component_candidate_types` 对“含 clinical_history + lab_result 两类资料要求的组件”产生的词表，单独一条 `lab_result` 事实使 `history.condition_present` 的 exists 求值返回 `TruthValue.TRUE`。这是**未登记的新反例**，详见 F1。

### 1. 对设计 §17.1.1 的裁定：同意方向，需改后执行

§17.1.1 对三种现有记录的定性经核源全部准确:`supported_requirement_ids` 仅校验“声明的编号在冻结范围内存在”(`app/agents/evidence_normalizer.py:1599-1619`)加发布时候选并集一致(`app/storage/fact_repositories.py:1207-1217`);`FactRuleLink` 是仅按 fact_type 精确相等建立的要求/组件索引(`app/domain/contracts/fact_rule_index.py:146-202`);`PredicateObservation` 被强制逐字段镜像 Evaluator 结果(`app/domain/gates/assessment.py:396-408`)。三者确实都不是已核实的原子条件语义对应。规格与 `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`(原子谓词字段表 ：119、节点绑定 ：114)不冲突，五步闭环方向正确。

需改点见 F4:规格未点名它自身要求的合同扩展，按本项目既往失败模式(工程审阅 §6 第 2 条“严格全拒/宽松全收摆动”)，不点名的后果就是又一层词表桥接改名的伪修复。

### 2. 发现(按严重性)

**F1 / P1(新证据，超出两个已登记 xfail):组件内跨资料类别泄漏 + 触发/例外共用词表，可产生错误的明确临床结论。**
`app/services/eligibility_review_projection.py:656-665` 的 `_component_candidate_types` 把组件**全部**资料要求的 fact_type 并集复制给触发**和**例外中的每个 `subject.attribute` 谓词键，且不过滤 due_stage。后果(已实证)：

1. 组件同时要求病史类和检验类资料时，一条无关检验事实即可使病史谓词 exists=TRUE;
2. 同一词表同时喂给例外谓词：一条无关 `clinical_history` 事实使触发 TRUE **且** `exception_documented` TRUE,经 `app/domain/gates/assessment.py:340-341` 净结果为 **EXCLUSION_NOT_TRIGGERED——受试者显示为不触发排除**。即当前实时工作台不仅会错报“触发”，还会借幻影例外错报“未触发”，两个方向都能产生明确错误结论。
3. 已登记的两个 strict xfail(`tests/v2/test_predicate_semantic_binding_boundary.py:26-33`)只覆盖单类别组件场景，未覆盖多类别并集与“例外被同词表放行”的合成场景。

根因:`EvidenceRequirement`(`app/domain/contracts/rules.py:279-297`)与谓词无任何关联字段，`_evaluate_atomic` 仅按 fact_type 选事实(`app/domain/expression.py:448-454`)。

**F2 / P1(结构性)：对象身份在求值链上不存在，“不同对象同值”“否认范围”两类反例无法表达。**
V2 发布事实有 `asserted_object`(`app/domain/contracts/facts.py:387`),但适配器 `adapt_clinical_fact_v2`(`app/services/eligibility_review_projection.py:196-212`)将其丢弃；Phase 3 求值合同 `ClinicalFact`(`app/domain/contracts/evidence.py:225-255`)无对象字段;`_evaluate_atomic` 从不比较谓词对象与事实对象，多事实唯一性检查也只按 `(value, unit, polarity)` 聚合(`app/domain/expression.py:496-499`)。§17.1“每个原子谓词必须知道所需对象…”在当前合同下不可满足。最小修复需版本化扩展求值链合同(或绑定记录)携带对象与来源角色。

**F3 / P1:实时与正式求值链不同源，§17.1.1 第 5 步“统一消费”没有任何现有接线。**
实时链:`eligibility_review_projection.py:691-714`(V2 `current_fact_heads` 校正链头 + 组件内 alias 词表)。正式链:`app/domain/gates/assessment.py:566-578` 用 Phase 3 `evidence_candidate.clinical_fact_candidates`,**无 alias、无 V2 校正链、不经 `current_fact_heads`**。正式链当前无生产调用方(仅 `gates/__init__.py` 导出，工程审阅证实 ReviewRun/FinalAssessment 实例为 0),但一旦接线，同一组件在两条链会得出不同结果(工作台经 alias 得 TRUE,正式重算按精确 fact_type 得 UNKNOWN,触发 `assessment.py:595-598` 的不一致拒绝)。恢复计划 T1 第 2 步要求的“唯一组件求值/缺口验证服务”尚未存在。

**F4 / P2(规格需改项)：§17.1.1 要求的字段与现有合同缺口未点名。**
a. `AtomicPredicate`(`app/domain/contracts/rules.py:183-235`)缺 §17.1(设计 ：292)要求的**量词**(任一次/最新/全部)、**时间角色**(事件时间 vs 记录时间 vs 资料有效期——t1-temporal-scope 会审已裁决需版本化 temporal-purpose 合同，六个 strict 预期失败仍在)、**极性期望**、**允许来源**(仅存在于 `EvidenceRequirement.required_source_types`,与谓词无关联)。规格应显式列出需扩展的合同与版本化方式，否则实现者会再次把语义塞进 fact_type 或同义词表。
b. 第 2 步“受限候选”没有落点合同与仓储。应显式声明：新增版本化 `PredicateBinding(候选/已验证)` 合同+仓储，纪律镜像 `fact_rule_index.py:94-115` 的内容哈希身份；不得复用三种现有记录改名。
c. 第 3 步的结构校验应点名复用件：发布侧交叉实体语义一致性与定位哈希校验(`fact_repositories.py:1184-1239`)、`validate_accepted_candidate_sources`、`_evaluate_time` 的部分日期算法(`expression.py:277-443`,不可重写)。
d. 第 4 步的过期失效键未具体化：绑定身份应含 `(predicate_id, rule_set_revision, authority 元组, fact stable_identity+revision, 冻结输入哈希)`,失效检测复用 `current_fact_heads`(`app/storage/active_facts.py:13-40`,含同修订号冲突 fail-closed)与 `FactCorrectionRepository.superseded_entity_ids`。
e. 触发/例外角色可从表达式位置确定性导出(predicate_id 在 RuleSet 内唯一，`rules.py:360-363`),无需改 `EvidenceRequirement`;规格宜写明，避免不必要的合同变更。

**F5 / P2:PredicateObservation 镜像检查与语义答案的冲突未设计拆分。**
`assessment.py:396-408` 强制镜像。§17.1.1 第 5 步禁止把语义答案伪装成确定性事实来满足该检查，但未给出拆分设计。最小修复：镜像检查拆为 (i) 确定性字段(身份/值/单位/日期/span)始终镜像;(ii) truth 字段按消费合同分支——semantic 谓词对照“已验证绑定集合+确定性计算”核验，模型声明 truth 不得覆盖代码算得的阈值/日期/布尔组合。

**F6 / P3:`_component_candidate_types` 不过滤 due_stage**,后续节点资料要求的类别也进入当前节点词表；与 `_summary_gaps`(`eligibility_review_projection.py:451-453`)的到期过滤不一致。

**F7 / P3(交叉引用，不重开):全窗外 FALSE 混淆“过期评估”与“时间要求不满足”** 已由 t1-temporal-scope 会审裁决保留六个 strict 预期失败，属 §17.1.1 时间角色合同范围，本报告不重复采纳或推翻。

### 3. 反例覆盖映射(设计 ：312 / 输入 ：40)

| 反例 | 当前状态 | 归属 |
|---|---|---|
| 触发有证据、例外无证据 | 失败(例外共用词表被放行，xFail 已登记) | F1 |
| 真实例外 | 合法路径存在(`derive_component_decision:340-341`),须保护不被全 UNKNOWN 消灭 | 实现验收 |
| 同一事实支持上下界 | `used_fact_ids` 聚合允许同事实多谓词，合法；绑定须允许 N 谓词/事实 | 实现验收 |
| 不同对象同值 | **不可表达**(对象字段在链上不存在) | F2 |
| 部分日期及时间角色 | 部分日期算法已有；时间角色缺失 | F4a/F7 |
| 否认范围 | 极性翻转存在(`expression.py:520-525`)但按类别整体作用，同类多对象混合极性直接 source_conflict;需对象级绑定 | F2 |
| 跨组件同谓词键 | 已修(组件内词表，测试在) | 保持回归 |
| 校正后过期绑定 | 检测件已备(`current_fact_heads`/`superseded_entity_ids`),绑定合同不存在 | F4d |
| 伪造定位 | 发布链有定位哈希校验(`fact_repositories.py:1225-1239`);绑定校验步骤须复用并重验 | 实现验收 |
| 双模型分歧 | 无绑定链可测；须隔离双源评测 | 隔离评测 |

### 4. 最小完整纵向实现顺序(每步复用件)

1. **冻结输入**：复用 `authority_from_active_episode`、`get_rule_set`+`project_clause_pack`(谓词原文经 `exact_source_clauses`)、`current_fact_heads`、`EvidenceLocatorRepository`、`EpisodeRepository`(锚点/节点)。新增：冻结清单合同(权威元组、rule_set_revision、谓词 id+原文、事实 stable_identity+revision+定位+摘录哈希)，按需计算，不新增调度器。
2. **受限候选**：在现有冻结任务/传输框架上新增一种有界任务(建议仿 `judgment_search_job_service` 的持久任务形态，而非塞进页级 normalizer——绑定是受试者级不是页级)，输出仅限“哪条既有事实的哪个属性对应哪个谓词+对象/否认范围/时间角色/出处”；复用 normalizer 式边界校验模式(`_validate_normalizer_semantics`)。双主读走 §8 既有双通道。
3. **独立验证**：确定性校验复用第 3 节 F4c 所列件；FactRuleLink 仅作候选收窄。结构通过≠语义证明。
4. **版本化保存**：按 F4b/F4d 新合同+仓储，走既有发布事务模式(`fact_publication_service` 式)，内容哈希身份，幂等可重建。
5. **统一消费**:`EvaluationContext` 增 `verified_bindings`;`_evaluate_atomic` 候选选择改走绑定，确定性比较/时间/冲突逻辑不动；投影服务与 `publish_assessment` 共用同一装配函数(T1 第 2 步“唯一求值服务”的落点)；`validate_assessment_candidate` 按 F5 拆分镜像。

### 5. 验证与批准边界

- **单测可闭合(无模型)**：全部结构校验、过期失效、伪造定位拒绝、冻结闭包、绑定后确定性求值、上表除“双模型分歧”外全部反例(“不同对象同值”“否认范围”依赖 F2 合同先落地)。
- **仅隔离双模型+留出集可验证**：语义对应质量(错误关联率、合法绑定召回，按设计 §13 分列指标)、分歧处置、§6.1 变形测试(重命名/换序/同值异时，SAR/D001 已见集+按受试者隔离留出集，不注入药名/阈值/编号)。
- **需用户批准**：实时工作台与正式链切换为自动消费新验证绑定(设计 ：294、:312 明确保留接入确认)；任何历史已发布布尔值改写；新增模型角色。

### 6. 最重要异议、决策点与给 Codex 的有界问题

1. **异议(最高影响)**：T1 的组件隔离修复被记为进展，但 F1 证明组件内并集词表仍能让一条无关检验事实把排除条款净结果翻成“未触发”。建议在绑定链落地前，把“例外谓词不经绑定不得经 alias 放行”作为**过渡护栏**单独立项——这不是“全部改 UNKNOWN”的终态修复，而是先切断错误明确结论的最危险方向(例外放行)，触发方向留待绑定链根治。是否接受该过渡护栏影响实时界面可见的“无法判定”数量，属用户可见权衡，需 Codex 裁定。
2. **决策点**：F2 的求值链合同扩展(asserted_object/来源角色)是版本化合同变更，建议纳入 T1 范围而非另开 slice——否则第 5 步统一消费无物可消费。请 Codex 确认。
3. **有界问题**：§17.1.1 第 2 步“使用当前产品模型适配层”存在两种读法:(a) 仅复用适配器传输层，新增一种受试者级有界任务(我的建议);(b) 在既有 normalizer 任务内加绑定输出。读法 (b) 会把页级 run 与受试者级绑定生命周期耦合，校正/重跑语义复杂化。请 Codex 择一，我将按选定读法细化第 2 步合同。
4. **安全临时路径**(若上述问题未决)：按本报告第 4 节顺序先做第 1、3 步的纯确定性部分(冻结合同+结构校验复用)，不接模型、不改消费链，不阻塞任何人。

### 7. 不确定性与未验证项

- 未审计前端消费细节与 `judgment_search` 全链(R07 范围，仅读到投影消费摘要一节)。
- 正式链无生产实例，F3 的“接线后必然分歧”是由代码路径差异推出的推断(证据：两处 `EvaluationContext` 构造参数不同)，无运行实例可直接复现。
- 未运行真实模型、未访问真实临床库；所有实证均为确定性构造。
- 本报告为工程/证据审阅，不构成临床、监管或用户-facing 验收；最终裁定权在 Codex。
