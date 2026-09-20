# Conference Output: r05-official-proposition-integration-20260915 - evidence_single_object

## Output

只读源码审阅已完成：覆盖"正式入排 `semantic_proposition` 声明 → 冻结输入 → 双路命题核实 → 资格消费 → 冻结计算 → 正式发布/报告"全链，并逐项核对了任务要求的九个关注点。总体结论：**链路骨架与保护性设计真实存在且大体自洽(原文闭包、双路独立身份、意愿≠履行、任一/全部/单次与范围见证、争议与窗口保守化、回执重建与版本钉扎均可追溯)，但发现 1 个呈现层错误(D1)、2 个功能性缺口(D2/D3)、1 个批级脆弱性(D4)及 3 个低级缺陷；不能宣告功能完整。** 未运行任何测试、未导入应用、未触碰产品服务。

### 一、链路核实结论(证据，均出自当前源码)

| 环节 | 关键证据 | 结论 |
|---|---|---|
| 命题声明约束 | `app/domain/contracts/rules.py:203-291`(仅 exists+无值/单位、不混研究者判断/频次);`app/agents/protocol_deconstructor.py:2009-2033` 同约束在 wire 层重申 | 命题不能伪装确定性计算 ✓ |
| 原文来源闭包 | `app/protocols/deconstruction_gate.py:3365-3419`(`SEMANTIC_PROPOSITION_SOURCE_NOT_CLOSED`);`app/domain/contracts/predicate_binding.py:266-272`(每段 `exact_source_clauses` ⊆ 已发布 `rule_source_text`,否则拒绝冻结);`source_status` 由原文字段存在性推导(`predicate_binding.py:147-153`) | 原文为逐字协议片段，非模型改写 ✓ |
| 双路核实 | `app/llm/proposition_evidence.py:40-114`(消息)、`117-161`(校验:命题哈希绑定、引文必须 ⊆ 本配对 locator 摘录、未来期间/整范围/研究者判断门);`app/services/proposition_evidence_comparison.py:9-42`(两路须不同 provider+model、同消息哈希;`agreement_key` 含方向/依据/范围/期间) | 双路独立身份成立 ✓ |
| 回执重建 | `app/services/proposition_evidence_receipts.py:35-44,83-128`(payload sha、输入重推导相等、逐路重放、summary 与存档逐字节相等、receipt sha 保存) | 历史哈希纪律 ✓ |
| 资格消费 | `app/services/qualified_proposition_evidence.py:28-92`(绑定同候选任务/上下文/四类哈希;方法评测钉扎 contract/prompt/summary/routes/consumer v5);`app/domain/contracts/proposition_method_evaluation.py:15-21`(v1 清单禁用于正式条件) | 跨版本授权不继承 ✓ |
| 冻结计算 | `app/services/qualified_binding_selection.py:492-513`(命题仅消费关系记录、selection 政策拒绝、single 完整性、日期资格);`app/services/predicate_proposition_calculation.py`(逐事实真值：争议组→`source_conflict`;`evaluate_time_constraint` 用合格 `date_range` 的 `fact.effective_date`+冻结节点锚点;窗外→UNKNOWN 不反证);`app/domain/proposition_observations.py`(ANY真/ALL假由单个明确 individual 见证；反方向需 universal+无缺口+无未知，ALL真另需 nonempty+逐字引用) | 与设计 §17.2 一致 ✓ |
| 发布与报告 | `app/services/frozen_review_publication.py:99-179`(授权重建+计算+FinalAssessment,`proposition_pair_gaps` 随观察保存);`app/services/review_history_service.py:396-416`(报告期重验命题身份与 locator 归属);`app/api/v2/review_history.py:426-450`(未核实原文单列“保留供查阅，不作为已确认依据”) | 未核实原件留存 ✓ |

未来意愿≠履行：`app/domain/contracts/proposition_evidence.py:32-40`(`ongoing_conduct`/期间未覆盖产生未决码，且 `:72-74` 禁止此时给出明确关系);确定结果携带 `prospective_statement_verified`,前端映射为“此处核实的是原文所记载的意愿或计划及其适用期间，不代表未来行为已经履行”(`frontend/src/domain/reviewConditionNotes.ts:11`) ✓。

### 二、缺陷清单(按影响排序)

**D1(中高·原因码污染，呈现错误)`app/services/predicate_proposition_calculation.py:79-82` + `app/domain/proposition_observations.py:14-17`**
单次(single)策略、范围未核实时，`combine_observations` 聚合观察自身的 reason_codes 作为 UNKNOWN 原因；而通过未来期间核实的确定观察，其 reason_codes 恰好是正向标记 `prospective_statement_verified`(非空)，使 `or ["observation_scope_completeness_unverified"]` 永不触发。结果：该条件显示“无法判定”，理由却渲染为“意愿已核实、不代表未来履行”——把肯定性说明当成未定原因，真实原因(范围完整性未核实)丢失。非安全性错误(方向保守)，但直接违反“逐项原因如实呈现”边界。
最小修正：该分支无条件附带 `observation_scope_completeness_unverified`(或在聚合时过滤正向标记)，不改变真值逻辑。

**D2(中·半衰期永不可判) `app/services/frozen_review_calculation.py:216-222`**
`EvaluationContext` 构造未传 `half_life_days`(恒为 `{}`),而 `calculate_frozen_review` 是正式审核唯一入口。解构器可产出 `half_life_multiplier`(wire `protocol_deconstructor.py:529`,门禁 `deconstruction_gate.py:2558-2567` 核对原文数字)，此类官方谓词(数值与语义两条路径,`expression.py:374-378`、`predicate_proposition_calculation.py:73`)在正式审核中只能永远 UNKNOWN `half_life_missing`。保守但从未在任何设计文档声明为已知限制。
最小修正：二选一——从版本化方案上下文接入半衰期数据；或在解构/发布门禁显式拒绝半衰期约束并登记限制，不静默产出永不可判条件。

**D3(中·命题证据任务对直接提交路径是可选的) `app/services/qualified_review_command.py:83-92,133-149` + `app/services/qualified_binding_selection.py:411-413,497`**
工作流 v5 会排程 `predicate_proposition_evidence`(`prepared_review_workflow.py:275,333-338`),但 HTTP 直提交通路不校验“冻结规则集含语义命题时必须附带命题证据任务/采用”。未附时 `proposition_relations=[]`,全部语义条件以 `semantic_evidence_unverified` 进入可发布的正式报告，且方法采用确认(`read_review_method_approval`)也不要求命题覆盖。方向保守(UNKNOWN 非错判)，但正式审核可带着“所有语义条件未判定”完成，且“未附任务”与“已核无一致”在结果上不可区分——正是任务书禁止的“以保护性 UNKNOWN 宣告完整”的形态。
最小修正：当冻结组件含 `semantic_proposition` 时，要求 predicate 族授权必须携带 `proposition_evidence`(或在发布载荷显式记录省略原因并单列呈现)。

**D4(中·批级校验脆弱性) `app/llm/proposition_evidence.py:148-156`**
单路对某个配对输出 universal 断言而非 any/all 政策(或无政策时输出范围确认)→ 整个 payload 校验抛错 → 该批双读失败。真实病历完全可能包含整范围陈述而方案声明 single/unresolved——模型持续如此时任务 `failed_final`,阻塞同批**所有无关配对**。失败方向保守，但违反“失败须限定影响范围”的恢复原则。
最小修正：将“政策不匹配的 universal/范围输出”降级为该配对 unresolved 记录(带原因)，保留身份/哈希/引文包含关系的严格批级校验。

**D5(低·选择层状态簿记不一致) `app/services/qualified_binding_selection.py:497`**
语义命题分支 `unresolved = [] if relations else [...]` 覆盖了 `_select_with_ordering` 已产出的原因(如 `observation_policy.mode == "unresolved"` 时 `:293-294` 的 `observation_selection_unverified`)——身份结果被记为 usable 且无原因。安全性由 `combine_observations` 对 mode 的复查兜底(最终仍 UNKNOWN+正确原因)，且 outcome 状态不单独持久化；但封闭材料内部状态失真，未来依赖 status 的消费者会误读。
最小修正：并集保留先前原因，不覆盖。

**D6(低·正式条件的逐缺口原因未上 DTO) `app/api/v2/review_history.py:445-450`**
官方命题缺口在报告 DTO 中只有固定句子；`gap.reasons`(分歧/期间/资格拒绝)仅经条件级合并原因间接可见。控制侧则逐缺口暴露 `reason_codes`(`:593-595`)。粒度不一致，存储无损失。
最小修正：给未采用项 DTO 增加 reason_codes,复用前端映射。

**D7(低·前端映射缺项) `frontend/src/domain/reviewConditionNotes.ts`**
`selected_observation_missing`、`no_usable_qualified_pair`、`event_date_not_qualified_for_selected_value`、`multiple_usable_pairs_without_selection_policy`、`identity_absent_from_qualification` 等码落入兜底句“本条件尚有未核实内容…”。可用性损失，非安全。

### 三、记录性边界(非缺陷，防止误读为完整)

- 语义命题的 `assertion_extent=unresolved` 记录即使双路 entails 一致，也不构成 any/all 的 individual 见证 → UNKNOWN(范围完整性)，符合设计，但意味着“单条明确支持”之外的多数情形仍为未定；**官方 any/all 的通过率将结构性偏低，评测时须按此预期**。
- `prospective_window` 仅触发声明期间核对，不另做日历核算(按设计留到后续节点)；确定结论只附“不代表已履行”说明。
- 提交通路允许的“无命题任务发布”(D3)在工作流 v5 之外；两入口的严格度不同。

### 四、对 Codex 的决策点与有界问题

1. **D1/D4 是否纳入本切片修复？** 两者均为小改动且不破坏身份/哈希；D1 影响用户可见文案正确性，建议本切片修；D4 需要定降级语义(unresolved 原因码命名)，建议随下一次 prompt 版本升级一并处理。安全临时路径：维持现状(方向保守)。
2. **D3 的产品意图**：正式审核是否允许在语义命题存在而命题证据未附时发布？若允许，需在报告显著位置单列“本项尚未进行原文含义核实”(区别于“已核未一致”)——请裁决走“强制附带”还是“显式省略标注”。
3. **D2**:当前任何真实方案是否含半衰期约束？若含，须先接数据再谈该类条件可用性；若不含，建议在门禁登记限制即可。我未查生产库(边界禁止)，无法自行判定。

### 五、总体判断

骨架可以支撑后续受控接入：授权-版本-回执-重建的不可继承链条闭合，未核实原件与历史哈希保留完好。但按任务书标准，当前状态只能报告为“链路已接线、存在上述缺陷、未经临床验收”；D1、D3 直接影响“逐项原因如实呈现”与“不得以 UNKNOWN 充当完成”，建议在任何正式发布许可前处理。
