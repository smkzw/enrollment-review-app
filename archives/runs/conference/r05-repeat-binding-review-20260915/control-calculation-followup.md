全部核对完成。以下为第四轮审阅报告。

# 会议输出： r05-repeat-binding-review-20260915 - evidence_single_object（第四轮：控制旁置计算/复查计数/图修复确认/原因码绑定）

## 输出

### 一、缺陷与备注（均低严重度；未发现高/中缺陷）

**K1（低——辅助与普通模式共用 contract 版本）**
`control_calculation_experiment.py:31` 的 `ControlCalculationExperiment.version` 仍为 v10，辅助模式仅靠 `selection_payload` 增加 `"purpose": "auxiliary-repeat-trigger/v1"`（:320-321）区分哈希域。普通路径 payload 字节与旧版一致（回归安全），但同一 version 字面量承载两种结构，未来消费者若只看 version 可能混淆辅助与普通的 `selections_sha256`。最小修订：辅助模式用独立版本字面量，或在 contract 上加显式 purpose 字段。

**K2（低——TRUE 附注混入条件原因码）**
`control_repeat_trigger_calculation.py:45-47` 将全部 `calculation.observations` 的 reason_codes 汇入条件结果，包括 `_proposition_observation` 对 prospective 情形在 TRUE 时返回的附注（`prospective_statement_verified`，`control_calculation_experiment.py:98-99`）。条件为 TRUE 时原因码含“已验证”字样，易被误读为验证声明（实际仅为记录）。最小修订：只汇入 `truth == UNKNOWN` 的观察原因，或过滤附注类码。truth 不受影响。

**K3（备注，延续上轮 J4）**：`control_repeat_trigger_calculation.py:56` 与谓词族同样直接哈希条件 dump、无子序归一。仅作记录锚，无消费比对。

**K4（备注）**：`expression.py:665` 的 `professional_judgment_missing` 分支未追加 `repeat_relation_unverified`（仅 :667-669 的 unverified 分支追加）。missing 与 unverified 是不同缺口类型，可不改；若求一致可同样条件追加。

**K5（语义前提，非缺陷）**：`repeat_observation_count.py:34-35` 的 `count_status="not_specified" → TRUE + repeat_count_not_specified` 是“次数维度无约束”的真，不是“次数合规已验证”；接线正式消费者时必须按此解读，否则会过度声明。

### 二、已确认边界（按分派点）

**1. `control_calculation_experiment.py` 重构**：`_evaluate_control_selection`（:137-329）承载原主体，新增 `repeat_triggers_only=False` 并返回 `(experiment, by_control)`；公开 `evaluate_control_layers_experiment`（:332-346）六参数签名不变、走默认路径——**普通四层路径逐行保留**（False 时身份投影 `:158-160` 与旧默认等价；layers 组合 `:303-306`；payload `:307-319` 无 purpose 键，普通哈希字节不变）。辅助模式：投影含旁置后再过滤 `layer == "repeat_trigger"`（:158-162），identities 恰为旁置原子；`layers=[]` 不组合最终层（:306）；purpose 键使选择哈希域独立（:320-321）。

**2. 控制旁置计算**：`evaluate_control_condition`（`control_layer_evaluation.py:70-77`）要求 expected 非空、组内原子 id 唯一、键集恰好相等、值为 TruthValue——`_any(_all(...))` 与 `compose_control_layers` 的 DNF 组合同构，不触 activation/applicability/obligation。`calculate_control_repeat_triggers` 走辅助模式；(control_id, atom_id)→identity 映射与目录同源无缺失面；`replacement_authorized` 恒 False（init=False，:19）；冲突来源保留（冲突组校验 :207-221、冲突事实强制 UNKNOWN :233-247、source_conflicts 记录 :229-230）。无上层调用（未接线）。

**3. `repeat_observation_count.py`**：纯供给采集组计数——参数校验拒绝按文档/行数累加（:28-33）；`unresolved` 或声明范围与计数范围不符 → UNKNOWN（:36-37）；**部分覆盖可证超上限**（:38-39，`FALSE/repeat_count_exceeded` 先于覆盖检查，单调正确）**不可证符合**（:40-41 UNKNOWN）；完整且未超才 TRUE（:42-43）；docstring 明示来源资格/范围归属/独立采集为调用者前提（:23-26）。无消费者。

**4. J1/J2/J3 修复核查（源码逻辑验证，非盲从）**：
- **J1**：`observation_relation_graph.py:70-84` 对每条 `preceding_observation` 边，从 child 的**其他**前次向其更早前次做 visited 防环闭包，达到 prior 即 `repeat_reference_kind_conflict`。方向推演：真实中间检查 M（prior→M→child）必在 child 前次集且其祖先含 prior → 正确捕获；prior 不可能出现在其后代的祖先闭包 → 无误报路径；无中间路径时同 (child, prior) 双 kind（首次复查，初查即紧邻上次）不触发——与分派描述一致。
- **J2**：`:97` `unclassified_fact_ids` 恢复为 v1 语义（`identifiers - linked`，两版本同义）；`:107-108` 新增独立 `origin_unresolved_fact_ids`（角色非唯一组成员）仅 v2 输出。
- **J3**：`repeat_trigger_calculation.py:53-55` 与 `predicate_proposition_calculation.py:30-32` 均改为显式缺失身份拒绝并附“须按当前版本重新核对”说明。

**5. 原因码与版本绑定**：`expression.py:666-669` 未核实确定性谓词原因 = 原有 `professional_judgment_unverified`/`observation_unverified` 之一，条件追加 `repeat_relation_unverified`（仅 `repeat_scheme` 非空）——真值仍 UNKNOWN、专业判断第一原因保留；求值器级守卫（:488-489）不变。`frozen_review_calculation.py:27` 升 `component-review/v23` 且 `:165` 强制相等——旧快照（v21）不可用新原因行为重算，行为变化绑定版本。

**不安全肯定结果检查**：`combine_observations` 空观察 → `UNKNOWN/"selected_observation_missing"`（`proposition_observations.py:8-9`）；single+非确定+scope 未证 → UNKNOWN（:14-18）；universal_ready 门控（:37-42）；命题关系冲突 → UNKNOWN（`control_calculation_experiment.py:93-95`）；复查计数部分覆盖不可证符合。观察/来源/时间/命题完整性假设在合同与聚合层均保守化。

**纯计算前提 vs 采用的区分**：三个新入口（谓词旁置 `repeat_trigger_calculation`、控制旁置 `control_repeat_trigger_calculation`、复查计数 `evaluate_repeat_count`）docstring 均声明 caller-owned 前提；`replacement_authorized` 与临床标志恒 false；全部无正式消费者——已知待办，不视为完成，未扩围实现。

### 三、剩余运行时不确定性（未验证）

- 全程只读：未运行 Python/内存构造/测试/应用/模型/浏览器；全部结论为源码推导，无运行口径结论。
- J1 新遍历（:72-84）的正确性为图方向语义推演（含有环图下 visited 保证终止），未构造数据实证。
- `_conditional_observation`/`_proposition_observation` 与 `combine_observations` 的全部分支组合未逐项枚举推演（沿用上轮已核结构，本轮聚焦增量）。
- `frozen_review_calculation` v21→v23 的完整差异未逐行比对（按分派聚焦原因行为绑定；`qualification_gap_policy_version` 维持 "unverified-predicate/v2"，:297）。
- 新入口无产品调用：最终结果采用、期限与次数消费者、方法审批均为待办；按用户决定，阶段测试推迟到完整构建之后，本报告不要求亦不声称测试通过。
