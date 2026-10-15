源审完成。核读了新操作数计算投影、更新后的绑定作业 v3、规格合同修订、表达式公开算术、组合器与守卫。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（源审：操作数计算桥）

## Output

### 一、链条现状（已核实）
候选作业 v3 现在对满足**结构条件**的候选即时执行条件算术：规格声明操作数与候选属性一致、deterministic 模式、模型自declared `object_correspondence=supported` 且 `attribute_correspondence=direct`（纯时间计算允许 `derivation_operand`），才对 (atom, fact) 调 `calculate_control_operands`，结果嵌入 `operand_checks`，全程 `accepted=False`（app/services/control_binding_job.py:89-117、:99、:124；注释 :101 明示“条件算术不是对模型对应的批准”）。`calculate_control_operands` 单次验证冻结输入、先验全部身份对再计算（app/projections/control_operand_calculation.py:39-45）；错误码前缀化（predicate_binding_job.py:90、150-175 + control_binding_job.py:65）。合同升 v3，旧载荷被入口拒绝（继承 `__call__` contract 检查）。语义/判断模式在 :76-77 显式返回“尚无可执行的确定性规格”，绝不伪装成算术；谓词频次/未来期字段 :79-84 fail-closed。

### 二、算术正确性专项（结论：无即时正确性 bug）
- **record_time**：恒返回 UNKNOWN（有值时 reason `source_calendar_date_unverified`，缺值 `date_or_anchor_missing`），不做 UTC 截断（control_operand_calculation.py:98-105）——正确。
- **PartialDateRange→DateValue**：以 `lower_bound + 原精度` 构造（:95-97）；`date_bounds` 按精度重建整月/整年（app/domain/calendar_dates.py:26-39），day 精度合同保证 lower==upper（facts.py:149-151），unknown 精度无界 → 提前 UNKNOWN（expression.py:306-315）。区间语义无损，无伪点日期。
- **值/时间分离**：时间早退分支保留 `value_result`（:85-92、:98-105）——“旧报告不证明阈值失败”在结构上成立。
- `evaluate_observed_value` 只做极性/单位/比较，无类型匹配，docstring 钉死选择权在上游（expression.py:456-472）。

### 三、真实缺陷（按优先级）
**P1（中）`time_result` 不携带声明用途，`source_validity` 用途被当成员/区间算术执行。** 只要原子有 time_constraint 就计算（:89-109），仅 `unresolved` 被拦截；规格校验仍允许 `operation=time_constraint + time_purpose=source_validity`（control_evaluation_spec.py:38-42）。这使评估通道对“来源有效期”重复立规，与 `ControlEvidenceSourcePolicy.result_validity` 双权威，正是 §17.3 禁止的换算；且 `ControlOperandCalculation` 无 purpose 字段，下游无法区分“成员判定”与“时效判定”。最小修复（二选一）：`_calculate_operand` 对 `time_purpose=="source_validity"` 返回 `unresolved_reason="来源有效期由资料政策通道执行"`；或把 `time_purpose` 冗余进 Calculation 供下游甄别。推荐前者（更小且封死误用）。
**P2（中）履约类义务原子携带 deterministic 规格仍会被计算。** 校验器与消费者均无 kind 防线（spec :62-99 无 kind；consumer :73-88 无 kind），仅提示词禁止（deconstructor :1225-1229）。`MUST_RECORD` 等履约原子的值算术结果会被读作履约真值并入 `obligation_group_truth`（control_layer_evaluation.py:128）。最小修复：消费者一行——义务原子 kind 属履约集且 `spec.operation` 非空 ⇒ `unresolved_reason="履约完成不产生确定性真值"`。
**P3（低）无约束仍允许 `unresolved`（spec :78），与提示词“没有时间约束才写not_applicable”矛盾**；消费者该分支文案“时间要求尚未核实，不可忽略”（:110-111）在无约束时误导。最小修复：校验器强制无约束 ⇒ `not_applicable`。
**P4（低·说明）** `declared_operand_matches` 只比对 `spec.operand_attribute`（control_binding_job.py:93）；值比较+附时间场景的 `time_operand_attribute` 未参与候选属性匹配——时间操作数是规格自有权属性，可接受，但值得注释钉死该不对称是有意的。

### 四、有界下一代码单元（进组合器的唯一缺口）
现缺的是**每原子规约器 + 隔离入口**，两者都是薄函数：
1. `reduce_control_atom_truth(per-atom calculations) -> (TruthValue, reasons)`：跨被选事实做 Kleene `ANY(AND(value_result, time_result))`；`time_result=FALSE`（窗外）⇒ 该事实**不具证明力**（跳过并记 `observation_out_of_window`），绝不单独产出原子 FALSE；无可证事实 ⇒ UNKNOWN `fact_not_observed`（缺失不得证明否定性条件）；窗口内值结论相互矛盾 ⇒ UNKNOWN `source_conflict`（不得任选第一条，镜像 _evaluate_atomic 的冲突纪律 expression.py:494-533）；唯一一致窗口内 FALSE ⇒ FALSE（观察反驳阈值，合法）；`unresolved_reason`/非 deterministic ⇒ UNKNOWN 连同原因。
2. 隔离入口 `evaluate_control_layers_experiment`：镜像 `evaluate_bound_component_experiment`（expression.py:576-616）——哈希冻结 control_sha256 + frozen_input_sha256 + 选择清单，规约器补齐**全部**原子真值（组合器要求完整集合，control_layer_evaluation.py:65-66），然后 `compose_control_layers`（:69）。**隔离入口 ≠ 最终接受**：不注册、不进生产、不翻 `accepted`；自动对应的采信仍走 §17.1.1 隔离评测与用户批准；两守卫保持（frozen_review_calculation.py:37-38；evidence_expectations.py:219-222）。
机械范围检查（已在位，无需扩展）：身份/事实冻结闭包（:44）、规格原文属于原子（:74 经 validate_control_atom_evaluation）、锚点仅取冻结 episode（:46-48）。保持显式未验证的：对象/语义对应（模型自declared 仅是算术资格，非证明）、规格语义保真（仅逐字包含校验）、来源资格（政策通道）、多观察选择正确性（规约器职责）。

### 未验证部分
纯源审：未运行作业/算术/规约；模型对 v1.9/2.0 提示与 correspondence 字段的实际行为未测；§17.1.1 隔离评测未执行；无任何生产消费。不构成临床或最终验收结论。
