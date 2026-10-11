源审完成。核读了新规格合同、四类原子的集成与序列化、三处水合、wire v4/提示 2.0、门禁 v4 与执行 v4 的入口拒绝、以及事实合同的日期属性。以下为报告。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object（源审：求值规格合同）

## Output

### 一、集成核验（通过项）
- **合同结构**：`ControlAtomEvaluationSpec` 三模式×operation/predicate 配对校验完备（deterministic⇔operation、value_comparison⇔predicate、时间计算须日期属性+已定用途），规格原文须逐项落在所在原子 span→excerpt 内（control_evaluation_spec.py:31-58、61-80）。
- **序列化/历史**：四类原子 `evaluation` 可选、缺省即剔除（protocol_controls.py:856-861、906-911、948-953；水合类继承草稿序列化器）；三处水合原样保留（:2817、:2891、:2938）；wire v4 两类原子必填并带 require_explicit 校验（protocol_control_deconstructor.py:463/471、533/545），两处转换保序传递（:2420、:2448）；门禁 v4 候选/发布两侧调用 `validate_control_evaluations`（protocol_control_gate.py:3968-3970、4264-4266）；执行 v4 在步入口拒绝旧 execution_version、检查点拒绝旧 gate_version（protocol_control_execution.py:839-842、:966）。历史载荷 decode 走 evaluation=None 早退。未发现旧序列化回归。
- **提示 2.0** 已明示：比较须直接表达本原子成立、不按 kind 取反；date_range/record_time 区分且不得以记录日期冒充事件日期；资料存在/签名存在/办结不证明履约（deconstructor :1224-1230）。

### 二、真实缺陷/设计矛盾（按优先级）
**D1（高）`source_validity` 用途可与 `operation=time_constraint` 并存——双权威冲突。** 校验只排除 not_applicable/unresolved（control_evaluation_spec.py:37-41），而 `time_constraint` 操作要求使用**原子自身**的 time_constraint（:79-80）。若该约束本是病史回溯窗而用途标为来源有效期，评估通道就会把回溯窗当报告有效期计算——正是 §17.3 明令禁止、且与 `ControlEvidenceSourcePolicy.result_validity`（逐证据的独立权威）重复立规。最小修复：`time_purpose=="source_validity"` ⇒ `operation` 必须为 None（仅作分类标注，实际时效由政策通道执行）。
**D2（高）无时间约束时允许 `unresolved`，与提示词语义自相矛盾。** 提示词规定“没有时间约束才写 not_applicable”（deconstructor :1227-1228），但校验允许“无约束 ⇒ not_applicable **或** unresolved”（control_evaluation_spec.py:75-76）——无约束时没有可待解决的用途，unresolved 是幽灵未知，会迫使消费者对不存在的约束做 UNKNOWN 处理。最小修复：无约束 ⇒ time_purpose 必须 `not_applicable`；unresolved 仅保留给“有约束但用途无法判定”的诚实出口（消费者规则须钉死：unresolved+约束 ⇒ 时间求值 UNKNOWN，绝不静默不过滤）。
**D3（中）履约类义务 kind 可携带带计算的规格——真值将被误读为履约。** 设计明令“不按 kind 自动选择模式、kind 不取反”（spec docstring :11、提示 :1225），这是对的；但结构上对 `MUST_RECORD/COMPLETE_OR_VERIFY/SCHEDULE_OR_VERIFY_VISIT/COMPLETE_BEFORE_ANCHOR/SELECT_BASELINE_VALUE/MUST_PROFESSIONAL_ASSESSMENT/VERIFY_RESULT_VALIDITY` 等履约类原子允许 deterministic 规格，无任何校验拦截。组合器 `obligation_group_truth=ALL(atom_truths)`（control_layer_evaluation.py:128）会让“记录存在”的真值直接顶替“义务已完成”。提示词禁令（:1229）无结构强制。最小修复（与既有原则一致、非按 kind 选模式）：门禁/规格校验对 obligation 层的履约类 kind 拒绝**带 operation** 的规格——履约不是命题，其规格只能 semantic/investigator；真值类 kind（PROHIBIT_*/REACH_CONDITION）不限。备选是新增 `proposition_role` 字段，但那超出最小修复。
**D4（中）investigator_judgment 模式与原子判断旗标零校验。** :51-52 只禁 predicate 内旗标；模式为 investigator_judgment 而原子 `requires_professional_judgment=False`（把普通诊断标成判断义务，§17.2 泄漏）、或判断旗标原子带 deterministic 规格（predicate 旗标缺省 False 即可绕过 :51-52）都合法。最小修复（单向绑定，避免反向硬编码上游过度标注）：`mode==investigator_judgment` ⇒ 原子旗标必须 True。
**D5（低）`operand_attribute` 对非 deterministic 模式必填而无约束**（:24）——semantic/investigator 模式被强制填一个无意义枚举值，等于逼模型编造。最小修复：改为 Optional，operation=None 时省略（序列化模式已具备）。
**D6（低）规格内 predicate 可携带 occurrence_window/prospective_***（rules.py:196-198 未被禁止）——与原子 time_constraint+time_purpose 形成双时间权威。最小修复：规格校验禁止这些字段非空。
**D7（低·措辞级）否定性存在命题无 comparator 形态**：Comparator 仅 eq/ne/gt/gte/lt/lte/in/not_in/exists（enums.py:34-43），“无X病史”类原子只能 semantic；提示词未明示，存在用 ne+哨兵值或反向 exists 误写的风险。最小修复：提示词/docstring 加一句“不存在性命题不得用比较器表达，须用 semantic 模式”。
**风格提示**：`model_serializer` 方法插在字段注解之间（protocol_controls.py:856-861 等）合法但易在重排时损坏，建议移至字段块之后。

### 三、消费者前置与边界
- `record_time` 在事实合同有数据源（facts.py:255），但现评估器只消费 `effective_date`（expression.py:291）——`operand_attribute=record_time` 的求值属消费者扩展点，不是合同缺陷；消费者实现前应对其 fail-closed。
- **不能称桥已建成**：尚无任何产品评估器消费该规格，两守卫仍在（frozen_review_calculation.py:37-38；evidence_expectations.py:219-222）。建消费者前的最小前置 = D1–D4 四项校验修补（均 ≤ 若干行，不动框架）；D5–D7 可同批或随后。
- 留 Codex 裁决：D3 采用“履约类禁 operation”还是新增 proposition_role；unresolved+约束的消费者规则（建议 UNKNOWN）是否同时写入 spec docstring。

### 未验证部分
纯源审：未运行校验/测试/模型；wire v4 实际模型产出未测；提示词遵循度未知；未做历史目录 decode 的运行时验证（仅源码推断）。不构成临床或最终验收结论。
