源审完成。核读了观察政策合同、实验 v2 全文、线内嵌校验、提示 2.1 增补、四个版本章与隔离面。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（源审：观察政策与实验 v2）

## Output

### 一、边界核验（通过项）
- **合同/序列化**：`ControlObservationPolicy` mode∈{single,any,all,unresolved}+scope+逐项配对来源，配对/重复/空白校验完备（control_evaluation_spec.py:14-30）；政策原文须落在所属原子 span→excerpt 内（:110-114）；发布侧对 deterministic 规格强制政策存在、原文不足须显式 unresolved（:108-109，经 `validate_control_evaluations` require_explicit 到达门禁 v5）。规格序列化在政策缺省时剔除字段（:54-59），旧目录 decode→None→再序列化不变，**历史哈希稳定**（可选字段保持 `control-atom-evaluation/v1`，沿用 affected_workflow_stage_id 先例）。
- **线5/提示2.1/执行5/门禁5**：线原子内嵌 `ControlAtomEvaluationSpec` 并以 require_explicit 重校验（deconstructor :461/:471、:535/:546）；wire_version 硬校验（:2536）；执行 v5（protocol_control_execution.py:115）与门禁 v5（protocol_control_gate.py:58）版本章在步入口/检查点拒绝旧任务；在途旧绑定作业由 `_verify_current` 的发布哈希比对自然失效。提示 2.1 覆盖：single/any/all 语义、“最近一次/复查替代/复杂时点→unresolved 并在 scope 保留要求”、“不按入选/排除/义务类别交换量词”、“无病史不得用占位值+ne 或反向 exists”（:1236-1241）。
- **隔离**：`control_calculation_experiment` 仅存在于自身模块，无任何生产注册/导入——无意外暴露。
- **条件算术正确性（重点核查项）**：空选择先于 any/all 判定为 UNKNOWN `selected_observation_missing`（实验 :33-34），**无空集真空真**；single≠1 → UNKNOWN（:38-39）；unresolved/无非确定性 → UNKNOWN，语义与判断模式不伪装成算术（:31-32、:36-37）；any/all 为正确 Kleene 语义（TRUE>UNKNOWN>FALSE / FALSE>UNKNOWN），决定性分支携带原因（:43-53）；`source_validity` 在读取 time_result 前即 UNKNOWN `source_validity_policy_unverified`（:62-64）；`event_membership` 窗外→UNKNOWN `observation_out_of_window`、绝不判 FALSE（:68-69）；`interval_condition` 的 FALSE 合法通过（纯时间 :70-73、值+时间 :79-80）；`time_calculation_missing/value_calculation_missing` 防御分支在位（:70-78）。选择清单：键必须等于全部原子身份集合、允许空清单（:100-101）、重复拒绝、`sorted` 拷贝不突变调用方（:103-106），全部 (atom,fact) 对先验后算（control_operand_calculation.py:39-45）。`accepted=False` 双层固定（实验 :22；计算 Literal[False]）。

### 二、发现（bug 级，均小）
**B1（低·审计保真）**：any/all 决定性分支只汇集“决定性观察”的原因（:46-48），终值分支更返回空原因（:53）——例如 any=TRUE 时另一事实的 `observation_out_of_window` 或值原因被丢弃，未决证据链不可回放。最小修复：三分支统一 `dict.fromkeys` 汇总全部观察原因（不改真值）。
**B2（低·残留）**：`ControlOperandCalculation` 仍会为 `source_validity` 用途**计算并存储** time_result（control_operand_calculation.py:89-109 无用途拦截），实验层虽在解释侧拦下（实验 :62-64），但直接读 `calculations` 列表的消费者仍可能把它当成员/区间结论使用。最小修复：`_calculate_operand` 对该用途返回 `unresolved_reason` 且不置 time_result（与上轮 P1 建议一致，尚未做）。
**B3（低·既有残留，非本轮引入）**：规格 :115 仍允许“无时间约束 + unresolved”（与提示“没有时间约束才写not_applicable”矛盾）；实验路径中该组合落在 :36-37 前的 :33/:31 分支，不会误算，但 `unresolved_reason` 文案会把不存在的约束说成“时间要求尚未核实”（control_operand_calculation.py:110-111）。最小修复不变：校验器强制无约束 ⇒ not_applicable。

### 三、缺失能力（与 bug 分列，按设计显式留白）
- 观察选择仅量化**所提供集合**：per-visit 分组（“每个访视各一次”）、最近一次、复查替代、N/M 计数无表示——均须以 unresolved 表达（提示已令保留于 scope），属待建能力而非缺陷。
- policy.scope 为自由 prose，无结构化访视/期间绑定——未来消费者只能靠 §17.1.1 验证链核对选择范围与 scope 的一致性，当前无机械检查（设计使然，记录在案）。

### 未验证部分
纯源审：未运行实验/规约/模型；提示 2.1 遵循度未知；§17.1.1 隔离评测与用户批准未执行；两守卫仍在（frozen_review_calculation.py:37-38；evidence_expectations.py:219-222），无生产消费。不构成临床或最终验收结论。
