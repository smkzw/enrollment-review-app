# 会议输出：qwen-bounded-completion-review-20260910 - evidence_single_object

## 输出

续审第十二遍（定向来源约束复核）。先**接受更正**：基线 response-3 的 EX-04 本有两个组件（现病史为独立组件），我上一遍“无现病史分支”的表述有误，撤回。本轮其余结论（频次缺失、来源绑定缺失）不受影响。

### 1. 源码修订评审（证据：边界干净，两处注意）

- **`protocol_output_response_format` 1012–1023**：仅改**生成期** schema——每次调用新生成 `model_json_schema()` 再改 `$defs.AtomicPredicate` 为双完备 anyOf 分支（基础 required+properties 各自完整复制 + 分别强制 source_clause/source_clauses），无共享状态突变、不动持久 pydantic 契约、无医学内容；compact/远端路径未触碰（979–1001）。这是对 live-04 实测教训（解码器忽略 anyOf 的并列兄弟约束）的正确工程响应，与 nonblank 案例同构：**约束要在解码文法层闭环，提示词层不可靠（live-02/03 双证）**。
- **`_frequency_repair_action`（gate:1088–1097）**：实现“先区分数值结构缺失与原文绑定缺失”的分化指引，零疾病/阈值硬编码；脚本已改为直接 import 该函数（`qwen_semantic_repair_diagnostic.py:27,48`），消除了脚本/产品文本漂移。live-02 回执证明分化文本已实际进入提示。
- `_repair_prompt` 保留 `include_frozen_context`，并在该模式下重新携带完整原 `_SYSTEM_CONTRACT`（:1485）。
- **注意一（共享回归面）**：152 聚焦通过，但 1421 全量回归止步于最后“完整分支展开”之前——anyOf 包装会改变一切内省 `$defs.AtomicPredicate` 的消费者；产品校验走 pydantic（不读此 schema）故主路径无恙，但该变更的回归覆盖尚未闭合，须分开表述、补跑后再冻结。
- **注意二（生成/解析轻微错位）**：任一分支满足即合法的 anyOf 允许两字段并存，产品解析层“source_clause/source_clauses 二选一”若仍强制，则生成期放行、解析期拒绝（fail-late，可接受但应记录）。

### 2. live-05 残余风险（证据，按优先级）

1. **现病史 `comparator=in` + 合成值**（comp[2]）：`values=['单纯疱疹','带状疱疹感染']`——原文枚举的是感染类型（“单纯疱疹、带状疱疹”），“带状疱疹感染”是拼合词；`in` 隐含对受试者事实值的成员测试，下游事实匹配中记录作“带状疱疹”的值可能不命中。属表达/归一层风险，非频次/作用域 gate 职责；建议留给事实匹配校验，不在此修。
2. **source_term 轻度合成**（‘单纯疱疹、带状疱疹感染’）与 comp[0] 摘录在“眼带状疱疹”后截断（连续逐字 ✓，但选择性省略复发性项——语义上合理：该示例已独立成件）。开放列举由“包括但不限于”保留 ✓；频次锚点正确（定义性 2y/min2 绑定自身子句、无伪造 time_constraint）✓；`_predicate_preserves_frequency` 全链通过（clause 含 spec、绑定词、窗值）= status remaining 0 的机制 ✓。
3. 单条款、单档、非排名、`clinical_acceptance:false` 维持正确。

### 3. 下一步优先级（建议：先离线，后换条款）

**优先完整门禁离线重放**（零模型成本）：live-05 只过了 frequency/scope 两项；应把 replacement 经 `_apply_semantic_repair` 合并回冻结草稿，跑全部十二项 `ProtocolDeconstructionGate` + 来源闭包 + 装配，现病史 in-比较子等残余风险才能在真实门禁面暴露。**通过后，下一次模型调用应换一个未校准条款/批次**（如 EX-05 类形状）验证绑定 schema 的泛化，避免 EX-04 过拟合（既有 checkpoint 已警示）。xgrammar“字段顺序敏感”仅记为解码兼容限度（编译成功 ≠ 完整兼容），不阻塞离线重放。

### 限度

未读 stream/私有推理；live-02–05 均单样本，不能推断档位/平台结论；1421 回归与最后变更的关系以所有权声明为准未经我复跑；本复核不构成对 EX-04 整条、正式表达路线或任何临床验收。
