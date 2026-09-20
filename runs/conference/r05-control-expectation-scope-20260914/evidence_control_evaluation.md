续审完成。本轮核实了：来源政策/有效期限合同（`ControlEvidenceSourcePolicy`、`ControlEvidenceOrigin`）、共享 v3 模板投影与存储再推导校验、控制模板的受试者投影拒绝点、DNF 四层合同、表达式求值器与 §17.1.1 绑定链合同、以及 frozen 审核守卫现状。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（续审：四层控制求值边界）

## Output

**总体判断**：模板/存储侧接线已按前两轮方案落地且校验严密；**求值侧的第一缺失合同是“控制条件原子的类型化谓词与绑定面”**——现有绑定链只认规则组件，控制原子今天没有任何不经 fact_type 匹配的求值路径。四层求值可完全复用现有三值引擎与 TimeConstraint 机制，无需伪造事实，也不需要新框架。

### 现状核实（代码事实）
- 来源政策三态+逐项原文闭合已入合同（`ControlEvidenceSourcePolicy`，app/domain/contracts/control_evidence_policy.py:9-28）；共享要求第三来源 `control_origin` 与 `control_validity_status/constraint` 成对入 `EvidenceRequirement`/模板并参与 v3 哈希（rules.py:284-311；evidence.py:163-203；evidence_expectation_templates.py:99-110、125-151）。
- 存储落库前从不可变发布**重新推导**并逐字段比对，政策不允许默认值顶替、不允许 legacy 窗口字段并存（repositories.py:1639-1681）；政策未断言（None）因布尔相等校验**根本无法入库**——unknown 政策留在控制目录/请求层，共享层只见真断言。这是正确的 fail-closed。
- 受试者投影对 `control_origin` 模板整体拒绝（evidence_expectations.py:219-222）；完整审核守卫仍在（frozen_review_calculation.py:37-38）。模板仅由发布投影派生、无受试者输入（control_evidence_requirements.py:37-39）——“不得按单个受试者适用性生成方案级模板”已结构性满足。

### 可复用接口（file:line）
1. **三值逻辑引擎** `_evaluate_logical`（app/domain/expression.py:116-137）——Kleene 语义，与 DNF“组间 ANY/组内 ALL”同构，四层组合直接可用。
2. **逐原子求值 + 显式事实清单** `_evaluate_atomic`（expression.py:448-537）、隔离消费入口 `evaluate_bound_component_experiment`（:568-608，哈希冻结组件+上下文、按谓词显式 fact_ids、无类别回退）——控制侧应泛化的正是这个形态。
3. **完整 TimeConstraint 机制** `_evaluate_time`（expression.py:279-445，含部分日期/边界）：控制条件原子携带的 `time_constraint` 与规则侧是**同一类型**（protocol_controls.py:853/895 引自 rules），一旦谓词类型化即整段复用；求值器只消费真实 `ClinicalFact`+锚点，**无需伪造事实或语义谓词**——唯一不得发生的是为凑求值而编造 predicate 的 value/unit。
4. **§17.1.1 绑定链**：`FrozenPredicateIdentity`（verbatim/unverified 来源状态，app/domain/contracts/predicate_binding.py:120-160）、`PredicateBindingFrozenInput`（:453+）、隔离候选作业（app/services/predicate_binding_job.py:1-40 "never clinical assessments"）。
5. **分支豁免/替代义务的语义已在合同冻结**：`ControlObligationGroup.applies_to_trigger_branch_ids`/`activated_by_exception_group_ids`（protocol_controls.py:1023-1035）、`ControlExceptionGroup.waives_trigger_branch_ids`/`activates_obligation_group_ids`（:1128-1141），草稿序位校验完备（:1273-1312）——组合器只需按这些显式 ID 工作，无需新语义。

### 决定性代码发现（非设计偏好）
- **D1**：控制条件原子只有自由文本 statement+来源闭合+TimeConstraint（protocol_controls.py:892-896），无 subject/attribute/comparator/value；而绑定链身份钉死在 `rule_component_id`+`official_code(IN|EX/REQ)` 且角色仅 trigger|exception（predicate_binding.py:63、120-131）——**控制原子无绑定变体**是第一缺失合同。
- **D2**：`ComponentEvaluation.applicable` 字段存在但从未计算（expression.py:80-84；evaluate_component :557 与实验入口 :605 均硬编码 TRUE）——适用性层有位无实现。
- **D3**：受试者侧今天是“全有全无”拒绝（evidence_expectations.py:219-222），覆盖可见性与适用性阻断尚不可分离表达。
- **D4**：legacy 别名回退仍是求值器在位路径（expression.py:42-44、452-459，R01 未闭）——控制求值绝不能走该分支。

### 最小四层求值设计
**第一缺失合同（建议先做）**：绑定链增控制原子身份——`(publication_id, protocol_control_id, condition_atom_id, 层角色 applicability|trigger|exception)` + 类型化谓词载荷（复用 `AtomicPredicate` 形状，值/单位必须逐字来自原子 source_excerpts，沿用 verbatim/unverified 状态）。义务原子**不进**谓词绑定：它们是行为义务，走证据覆盖+modality 处置，不做真值比较。

**层组合器（纯函数，泛化实验入口）**：
- 适用性：`applicability_expression` 缺省=TRUE；含 UNKNOWN 原子 → 整体 UNKNOWN → 控制行呈现“适用性未确认”，证据保持“已请求/已观察到”但**不产生 absent 阻断**；FALSE → 不适用、不出要求。**证据覆盖观察到 ≠ 适用**（两者输入与记录分离；适用性只吃绑定验证过的事实，绝不吃期望行——防“从证据匹配反推适用”）。
- 触发分支：逐组求值；命中的分支按 `applies_to_trigger_branch_ids` 选择义务组（空=默认路径）。
- 例外：逐组求值；豁免只作用于其显式 `waives_trigger_branch_ids`（分支级，不整控失效）；`activates_obligation_group_ids` 激活的替代组仅当该例外为 TRUE 时生效，绝不是默认组的 OR 兄弟（合同注释已明）。**例外 UNKNOWN 不得视作满足**——触发维持并标注“例外待证”（与 §17.1“只有真正满足例外的证据才解除触发”一致）。
- 义务：逐原子、逐 modality 处置——MANDATORY 未满足且（适用 TRUE+触发生效+未被豁免）→ 阻断缺口；RECOMMENDED/BEST_EFFORT 未满足 → 审阅中的建议项，**永不作为排除或阻断**；PROHIBIT_* 按条件求值；MUST_RECORD/MUST_PROFESSIONAL_ASSESSMENT 走期望/判断检索通道。结果合同按原子展开（类似 `predicate_evaluations` 字典），**不做控制级单一 flag**。

**覆盖与资格分离**：把 evidence_expectations.py:219-222 的整体拒绝改为条件投影——允许 observed/observed_weak 覆盖报告（文档层面真相与适用性无关）；absent 仅当独立的适用性投影记录为 TRUE 时才成阻断缺口，否则显示“适用性未确认，不判缺失”。

### 设计选择（源码不能裁决，留 Codex）
1. 类型化谓词经 wire 水合入目录（推荐：可门禁、可哈希冻结）还是仅在绑定时综合、目录保持自由文本。
2. 例外 UNKNOWN 时整体未决 vs 触发维持+标注（我推荐后者）。
3. 适用性结果的承载：独立追加式投影（推荐，不动 `EvidenceExpectationV2` 不可变合同）vs 期望行内字段。

### 实施顺序与优先风险
顺序：① 绑定链控制原子身份+类型化谓词合同 → ② 泛化 `evaluate_bound_component_experiment` 为控制 DNF 隔离消费（含 TimeConstraint 复用、禁走别名回退）→ ③ 纯函数层组合器（分支豁免/替代/UNKNOWN/modality 规则）→ ④ 以独立适用性投影替换单点拒绝，覆盖与阻断分离 → ⑤ 接入 frozen 上下文与报告后才可评估撤销 frozen_review_calculation.py:37-38 守卫（最终集中验证前保持）。
风险：R1 谓词综合是模型辅助步骤，必须先过 §17.1.1 隔离评测，未过不得进生产消费；R2 适用性误吃覆盖行造成“证据匹配→适用”泄漏；R3 例外 UNKNOWN 被当满足而错误解除触发；R4 报告/前端把逐原子 modality 折叠成控制级“符合/不符合”，建议项被渲染成排除；R5 政策未断言的控制无共享要求行（存储拒绝），报告层必须显示“来源要求未断言”而非静默消失——注意**协议侧未断言（policy unknown）与受试者侧资料缺失（absent）是两种状态**，呈现与统计都不得互替。

本轮为只读工程审阅：未做任何实现、测试、导入或运行；不构成临床或最终验收结论。
