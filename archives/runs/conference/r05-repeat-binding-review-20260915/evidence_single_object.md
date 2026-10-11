所有证据已闭合。现在整理并返回完整审阅报告。

# 会议输出： r05-repeat-binding-review-20260915 - evidence_single_object

## 输出

### 审阅范围与方法（披露）

- 完整精读初始读集全部 14 个文件（`protocol_deconstructor.py` 按指示用 `rg` 定位复查/`predicate_refs` 段落后精读相关完整函数与提示合同），并沿直接导入补读了必要相邻定义：`repeat_scheme.py`、`clause_pack.py`（合同+投影）、`predicate_binding_input.py`（`_frozen_component`）、`component_review.py`（选择透传）、`review_method_evidence.py`、`judgment_gap_selection.py`、`eligibility_review_projection.py`（`clause_to_rule_component` 及调用点）、`binding_qualification.py`（资格提示）。
- 全程只读：未写任何文件、未运行测试/应用/模型/浏览器、未读临床原件或凭据。为验证核心缺陷假设，执行了 3 次最小内存内 pydantic 构造（无文件写入，仅构造 `RuleComponent` 验证器行为），下文明确标注。
- 会议上下文与主会场计划文件均为未填模板（TODO），实质审阅依据为任务提示与源码。

### 一、特别检查项核验结论（全部成立，源码证据）

**1. 附加 `identity_outcomes` 被保留，`predicate_fact_ids_by_component` 仍只含正式触发/例外 —— 成立。**
- `app/services/qualified_binding_selection.py:586-594`：对 `_expected_predicate_identities`（遍历 `component.binding_predicates`，含 `repeat_trigger` 角色，`:185-202`）的**每个**身份（含复查触发身份）都 append `QualifiedBindingIdentityOutcome`；`:595` 注释明确 "Auxiliary checks retain outcomes without changing eligibility inputs"。
- `:596-597`：`if meta["role"] != "repeat_trigger": predicate_map[...] = list(fact_ids)` —— 组件清单**只收** trigger/exception。
- 下游结构性印证：`app/domain/expression.py:621-630` `evaluate_component` 的 `atoms` 仅来自 `component.expression` + `exception_expression`，且 `set(predicate_fact_ids) != expected` 即抛错——复查谓词 ID 从结构上无法进入求值清单。`frozen_review_calculation.py:238-243`（`unverified_by_component` 只遍历 trigger/exception）与 `predicate_proposition_calculation.py:24`（命题计算同样只遍历 trigger/exception）一致。

**2. `repeat_relation_unverified` 未解禁 —— 成立，四层防线齐备。**
- `qualified_binding_selection.py:44-47`：`_AUTHORIZATION_WAIVED_REASONS` 仅含 `evaluation_activation_absent`、`clinical_adoption_not_authorized`，授权**不能**豁免复查未核实；`QualificationAdoptionAuthorization` 合同也无任何复查相关豁免字段（`contracts/qualified_binding_selection.py:38-99`）。
- `_select_with_ordering`：谓词侧 `:280-282`、控制原子侧 `:290-291` 对带 `repeat_scheme` 的条件提前返回 `["repeat_relation_unverified"]`；主循环在语义命题分支之后再次强制附加（谓词 `:555-557`、控制 `:665-667`），不可被命题关系冲掉。
- 求值器兜底：`expression.py:488-489` `_evaluate_atomic` 对任何 `repeat_scheme` 谓词直接 `UNKNOWN/repeat_relation_unverified`。
- 消费端缺位：`result_use`/`result_combine` 全库仅出现在合同与解构器提示中，无任何计算消费者——复查采用确实未实现，而非被隐藏解禁。

**3. 不进入最终入排表达式 —— 成立。**
复查触发条件只存在于 `repeat_trigger_conditions` 旁置字段（`rules.py:422-436` 明确 "Ancillary expression; never an eligibility trigger or exception"；`validate_repeat_trigger_conditions` 禁止混入、禁止共用身份 `:439-466`）；候选提示明确其辅助性质（`predicate_binding_candidates.py:151-153`“仅描述何时允许或需要复查，不构成新增入排标准，不表示已获准复查，也不决定采用哪次结果”）且要求逐身份独立对应（`:136-137` required identities 含复查身份；`:218-220` 强制完整覆盖）。

**4. 不把旧评测授权套用新提示或算法 —— 成立。**
- `review_method_evidence.py:11-27` `require_evaluated_binding_method` 将 `verified["candidate_method"]`（候选任务类型/合同/提示版本/批次提示版本/双路路由）、当前资格合同/提示版本/汇总版本、当前消费算法版本（v16）与评测 manifest 逐字段比对，任一不符即 `ScopeViolationError`。
- `qualified_binding_selection.py:165-166` 拒绝非当前消费算法版本的授权；`:136-182` `_validate_authorization` 要求已保存 ACCEPTED gate 且哈希、实体引用、路由逐项一致；`binding_qualification_support.py:991-1095` 用当前代码重建消息哈希与回执比对，提示内容变化（含本次复查上下文增量）会使旧回执不可复用——fail-closed。
- 候选侧同理：`binding_qualification_support.py:359-364` 强制候选任务合同/提示版本为当前 `_PREDICATE`/`_CONTROL` 规格表版本。

**5. 复查旁置条件进入冻结身份/候选/资格上下文的接线 —— 成立。**
冻结侧：`contracts/predicate_binding.py:64` 角色含 `repeat_trigger`；`:242-265` 从哈希覆盖的条件表达式派生 `repeat_trigger_predicates`（不持久化第二份可编辑副本）；`:268-271` `binding_predicates` 注释 "Conditions needing evidence, not the final eligibility expression"；组件哈希纳入条件材料（`:183-184, :217-219`）。资格侧：`binding_qualification_support.py:310-323` 对 `repeat_trigger` 角色附加完整 `repeat_trigger_condition` 与 `repeat_owner_predicate_ids`；来源政策按 `predicate_refs` 显式归属解析（`:120-165`），与解构器提示“复查条件的资料归属须独立核实，不得继承原入排条件的来源要求”（`protocol_deconstructor.py:458`）一致。汇总工件恒 `accepted=False / authorized_clinical_adoption=False / clinically_qualified=False`（`:882-884`）。解构侧 wire `predicate_refs` role=repeat_trigger+condition_id 解析与去重校验完整（`protocol_deconstructor.py:2365-2418`），谓词 ID 重映射覆盖复查条件根（`:2916`），资料要求引用可正确重映射（`:2974-2977`）。

### 二、缺陷与建议（按影响排序）

**D1（高，真缺陷/集成遗漏——已用内存构造复现）**：条款包投影与求值侧重组丢失 `repeat_trigger_conditions`，使使用了本增量特性的方案在计算路径上崩溃。
- 证据链：`app/projections/clause_pack.py:111-128` 投影 `ClausePackClause` 时原样保留 `expression`/`exception_expression`（谓词携带 `repeat_scheme`）但**不投影** `repeat_trigger_conditions`；`app/services/eligibility_review_projection.py:801-813` `clause_to_rule_component` 重组 `RuleComponent` 时同样不传条件。
- 后果一（条件性复查）：所有者谓词 `repeat_scheme.trigger_condition_id` 非空时，`rules.py:447-459` 在重组时抛“复查要求引用的触发条件不在本组件内”。内存构造验证：同一表达式带条件构造 OK，去掉条件即抛该错。
- 后果二（复查归属资料要求）：资料要求 `predicate_ids` 引用复查谓词（wire `predicate_refs` role=repeat_trigger 是本增量明确支持的能力）时，`rules.py:492-514` 抛“资料要求引用了本组件不存在的谓词”——独立复现，即使所有者无复查方案也触发。
- 影响面：`frozen_review_calculation.py:250` 与 `eligibility_review_projection.py:725` 两条生产路径，均无守卫。fail-closed（拒绝而非误算），但使用复查特性的方案整条审核计算被阻断——而绑定链（`_frozen_component`，`predicate_binding_input.py:133,147` 保留条件）恰恰是为这些方案新建的。
- 建议 remediation（供 Codex 决策）：(a) `calculate_frozen_review` 手中已有 `rule_set` 且 `assert_qualified_selections_match_review_context` 已证明冻结组件与规则集逐字一致——重组时可按 `rule_component_id` 从 `rule_set` 补回条件，保持确定性；(b) 或升级条款包投影版本携带旁置条件；(c) 若判定计算路径支持不在本增量范围，则必须在发布 gate 或解构 gate 显式阻断“条件性复查/复查归属资料要求”进入已发布规则集，并在任务记录声明该限制，不能留成运行时崩溃。
- 分类问题（见“决策点”Q1）：这是真正错误还是已声明的后续未实现——源码与任务记录中均未见该限制的声明。

**D2（中，遗漏）**：本增量无任何测试锚。`tests/`（355 个文件）中 `repeat_trigger`/`trigger_condition_id` 零引用。D1 这类合同级构造失败，一个最小重组往返测试即可拦截。建议补：冻结身份派生、候选完整覆盖（含复查身份）、选择排除（map 不含复查 ID）、`repeat_relation_unverified` 不可豁免、条款包重组往返。

**D3（低）**：资格核对提示（binding-qualification/v4）无任何复查专用指引，而候选提示有；`role: "repeat_trigger"`、`repeat_trigger_condition`、`repeat_owner_predicate_ids` 随 `parent_source_context` 静默进入提示载荷（`binding_qualification.py:101-107`）。爆炸半径低（复查身份结果只进辅助 outcome），但双路判断可能不一致。建议：在资格提示补一段与候选提示同口径的复查辅助性质说明；同时注意 `parent_source_context` 内容变化未伴随提示版本提升——对本增量无实际影响（整条链为新增、无旧回执），但若未来再改上下文应同步提升版本以保持“旧评测不套新提示”的可读性。

**D4（低，可观测性）**：带 `repeat_scheme` 的正式条件最终以未核实落地时，组件求值原因码走 `expression.py:664-675` 的通用 `observation_unverified`，具体的 `repeat_relation_unverified` 只保留在 `identity_outcomes.unresolved_reasons` 与求值器兜底路径。读者/负责人在组件结果层面看不到“因复查关系未核实而未知”。建议把 outcome 的未核实原因传播进 `predicate_evaluations` 原因码或投影层说明。

**D5（备注，非缺陷）**：`requires_proposition`（`qualified_binding_selection.py:433-440`）与语义命题改写分支（`:523-554`）对 `repeat_trigger` 身份同样生效——复查谓词可带 `semantic_proposition` 并产生可用的辅助 outcome 与存续的 proposition_relations，但 `calculate_predicate_propositions` 只遍历正式条件，永不消费。与“附加结果仅辅助”一致，建议作为有意设计记录在案。

### 三、决策点与有界问题（致 Codex）

- **Q1（阻塞 D1 定性与修复路线）**：条款包/重组层对复查条件的支持，应在本增量内修复（方案 a/b），还是判定为后续未实现并在发布 gate 显式阻断+文档声明（方案 c）？为何重要：决定 D1 是“必须修复的集成错误”还是“已声明的范围外”，两者对当前交付的验收口径不同。安全临时路径：按方案 c 先在 gate 阻断含条件性复查或复查归属资料要求的规则集发布，使系统保持 fail-closed 且可解释。
- **Q2（次要）**：D3 的资格提示补文与版本策略是否纳入本增量，还是与 D2 测试一并排入紧后任务。

### 四、结论

本次增量在**绑定链内部**（冻结身份→候选→来源资格→选择→命题/书面判断辅助）的复查旁置条件接线与边界承诺经源码逐点核实成立：复查身份进 `identity_outcomes` 但绝不进 `predicate_fact_ids_by_component` 与最终表达式；`repeat_relation_unverified` 四层防线且不可被授权豁免；旧评测/旧提示/旧算法无法套用（全部 fail-closed 字段级比对）。**主要缺口在计算侧**：条款包投影与 `clause_to_rule_component` 未同步携带旁置条件，导致使用本增量特性的方案在两条生产计算路径上构造即抛错（D1，已复现），且全部增量无测试覆盖（D2）。以上不宣称临床、浏览器或最终用户验收；未验证项：任何运行时行为（未运行测试/应用/模型）、`tests/` 之外的回归资产、以及会议上下文中未提供的既定范围声明。
