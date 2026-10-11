# Conference Output: r05-observation-scope-design-20260915 - evidence_single_object

## Output

只读审阅完成。全程未改文件、未运行测试/模型/数据库/浏览器、未派发子任务、未扫描病例目录。以下按“证据 → 决定性源码问题 → 建议 → 最小方案 → 模型步骤论证 → 决策点”组织；行号以当前工作区文件为准。

### 1. 证据基线（源码事实，非推断）

完整读取：`app/domain/contracts/control_evaluation_spec.py`、`app/domain/contracts/proposition_evidence.py`、`app/llm/proposition_evidence.py`、`app/projections/control_calculation_experiment.py`；消费链 `app/services/qualified_binding_selection.py`、`app/services/qualified_proposition_evidence.py`、`app/services/proposition_evidence_input.py`、`app/services/proposition_evidence_receipts.py`、`app/services/proposition_evidence_comparison.py`、`app/services/frozen_review_calculation.py`、`app/projections/control_atom_binding_input.py`、`app/projections/control_review_outcome.py`；设计文档 §17（含 17.1.1/17.2）与恢复计划 T3/T5。

现状与任务“已知”陈述一致，并可在源码精确定位：

- 量词单向见证已实现：`app/projections/control_calculation_experiment.py:58-62`（ANY 见 TRUE、ALL 见 FALSE 即决）；反方向落到 `:69` 的 `UNKNOWN + observation_scope_completeness_unverified`。
- single 双路可核实：`_scope_supported`（`:101-108`）要求 main-A/main-B 两路 `scope_correspondence == "supported"` 且有非空逐字 `scope_quote`；`agreement_key` 含 scope 判断（`app/domain/contracts/proposition_evidence.py:47-50`），两路 scope 判断不一致即整体 `disagreement`，不会进入消费。
- 最近/复查无表示：合同 mode 仅 `single/any/all/unresolved`（`app/domain/contracts/control_evaluation_spec.py:18`）；解构提示明确指示“要求最近一次、复查替代或复杂时点选择尚不能表示时用 unresolved”并保留原文（`app/agents/protocol_control_deconstructor.py:1239-1241`）。
- 语义核实提示 v3 已在**同一次双读**中逐配对输出范围判断（`app/llm/proposition_evidence.py:66-71`），并已内置反滥用护栏：不得因批次只有一条配对断定仅一次观察、不得从原文未提及推断否认、无政策时不得补范围确认（`:69-71`，校验在 `:100-103`）。

### 2. 决定性源码问题（决定方案形态，建议必须处理）

**D1（语义缺口的核心）：范围完整见证的证据已经存在且已付费，但 any/all 模式完全不消费。**
`_proposition_observation` 只在 `mode == "single"` 时检查 `_scope_supported`（`app/projections/control_calculation_experiment.py:91`）；`scope_verified` 也只对 single 计算（`:239-244`）。因此一条**原件中明确覆盖整个政策 scope 的总结性陈述**（如体检总结/病史否认覆盖“全部病史范围”），即使双路一致给出 `supported + 逐字 scope_quote + agreed relation`，也无法落 ANY-false/ALL-true——这正是任务要求区分的第一类语义。证据在 `proposition-evidence/v3` 每次双读中都已产出并被 agreement_key 双路锁定，只是计算端丢弃。

**D2：`scope_correspondence: "partial"` 无任何消费者。**
grep 全库确认：`partial` 仅在合同定义（`proposition_evidence.py:15`）与提示中出现；`_scope_supported` 只认 `supported`。双读已为部分覆盖付出判断成本，但“范围不足时报告具体缺项”无法引用已见部分。这是纯消费端遗漏。

**D3：逐配对的具体未决原因在计算/报告中不可见。**
`unresolved_proposition_pairs` 存入 selection material（`app/services/qualified_binding_selection.py:543-548,595`）后无任何下游消费——`calculate_frozen_review` 只从 `identity_outcomes` 取 `status == "unresolved"` 的原子原因（`app/services/frozen_review_calculation.py:191-197`）。后果（推论，基于上述源码）：ALL 语义原子若有 1 条候选配对双路 relation 分歧，该配对被排除出 fact_ids，原子只报泛化的 `observation_scope_completeness_unverified`，具体哪条配对失败、为什么失败在冻结计算与报告中消失。另有合同形态限制：`evaluate_control_layers_experiment:187-192` 要求 `unverified_atom_reasons` 只能对应**空选择**原子，因此“部分配对已决 + 部分配对未决”的原子上无法把逐配对缺口送进计算。

**D4（结构性，任务已知）**：无 latest/retest 选择模式；且确定性 any/all 原子天然不能用总结性见证（总结陈述是 assertion_basis 语义，不是可比较的类型化数值），其反方向完整只能靠结构化成员原子（见 §4 S2）。

### 3. 建议（非决定性，可后置）

- B1：`identity_coverage` 与 summary 中硬编码的 `observation_scope_verified: False`（`app/services/proposition_evidence_input.py` 末段、`app/services/proposition_evidence_receipts.py:78`）在 D1 落地后语义会失真（任务级仍 False，记录级已有见证）；建议改为不由输入/汇总层携带该布尔，避免两处真值来源。
- B2：ANY 模式下“具体 TRUE 见证胜过相反总结否认”是见证语义的正确结果，但两条**方向相反的 scope-complete 见证**并存时应显式报 `scope_witness_conflict` 而非静默取决胜方向（见方案优先级第 2 条）。
- B3：`_proposition_observation:96-97` 对 `interval_condition` 假值直接给命题 FALSE、对 `source_validity`/`event_membership` 保持 UNKNOWN 的区分是正确的，方案不触碰；评测中应各留一例防回归。

### 4. 最小可落地方案（通用，无项目/疾病/药物/阈值硬编码）

**第一段（仅消费端，零模型改动、零新任务）：**

1. **S1 总结性范围见证（对应 D1）**：在 `evaluate_control_layers_experiment` 内对非确定性原子的每个 `(identity, fact_id)` 复用 `_scope_supported` 计算 `scope_complete`，`_conditional_truth` 的聚合优先级改为：
   ① 具体决胜见证不变（any+TRUE / all+FALSE，`:58-62` 原样）；
   ② 否则若存在同向 scope-complete 见证（全部范围完整记录 agreed 且方向一致）→ 反方向由见证落定（ALL-TRUE / ANY-FALSE）；两向见证并存 → `UNKNOWN + scope_witness_conflict`；
   ③ 否则逐记录 UNKNOWN 原因照旧透传；
   ④ 否则维持 `observation_scope_completeness_unverified`。
   关键边界（回应任务“不能把一条范围引用当临床完整”）：见证证明的是**该原件显式主张了范围级内容**（逐字 scope_quote + 双路一致），不是“档案检索完整”；决胜反例、来源冲突组（`:232-235`）、两路 scope 分歧仍然照常压倒或阻断见证。这与 single 模式现行的信任模型完全相同，未扩大授权面。
2. **S4 具体缺项（对应 D2+D3）**：新增计算入参 `proposition_pair_gaps: dict[identity, list[{pair_id, fact_id, reasons}]]`（来自既有 `unresolved_proposition_pairs`，校验其配对属于冻结输入且 fact_id 不与已选重叠；不触碰 `unverified_atom_reasons` 的空选择约束）；聚合落到③/④时合并这些具体原因。`partial` 记录在无见证落定时以 `scope_partially_covered` + 既有 lanes 引文进入原因集。有限枚举成员缺失（成员原子 single 模式的 `no_usable_qualified_pair / identity_absent_from_qualification` 等数据侧原因）与开放范围语义缺口由此天然可区分；要求级检索完整后按 §17.2 第三行纪律直接报告缺项，不等待用户确认。
3. **版本化**：`ControlCalculationExperiment` 增 `v9`（selection_payload 纳入 pair_gaps，哈希变化）；`frozen_review_calculation.EVALUATOR_VERSION` v12→v13（旧冻结审核仍按 v12 原样重放，`:163-167` 的版本闸门已保证）；`select_qualified_relations` 若输出 partial 感知原因则 `PROPOSITION_CONSUMER_VERSION` v2→v3。`QUALIFIED_BINDING_CONSUMER_ALGORITHM` 与 `proposition-evidence/v3` 提示**不动**——无任何模型载荷变化。原子身份含完整 atom dump（`app/projections/control_atom_binding_input.py:33-45`），历史发布身份不受影响。

**支持/不支持的语义（第一段后的诚实边界）**：
- 支持：原件显式覆盖政策 scope 的总结性陈述落定 ANY-false/ALL-true（S1）；有限枚举集合经结构化成员原子的逐项缺失报告（S2 的表示，见下）；部分覆盖与逐配对失败原因进入缺口报告（S4）；检索完整后直接报研究者判断/观察缺失。
- 不支持：从“页面全读/候选遍历完”推完整（设计上不可能，④恒守）；开放 scope 的**未覆盖子项命名**（需新结构化模型输出，明确推迟，报告改为引用政策 scope 逐字原文 + 指明何种证据可落定）；确定性 any/all 原子的总结性见证（D4 边界，书面陈述无法做类型化比较）。

**第二段（S2 正式化 + S3，涉及解构提示版本，须独立评测与采用授权后方可采信）**：

- **S2 有限观察集合**：不新增政策字段。解构提示下一版明确：方案原文枚举有限观察集时，在 ALL 组内逐成员发 single 原子（组复合 `_all` 已保留逐原子真值与 UNKNOWN 传播，`app/domain/control_layer_evaluation.py`），不得发 any/all 原子。完整性=每成员可解，缺项=成员原子 proposition+逐字原文，全部复用既有机制。
- **S3 最新/复查**：`ControlObservationPolicy` 增 mode 值（如 `latest_within_scope`），scope 保留“以最近一次/复查为准”逐字原文；走 spec 版本 `control-atom-evaluation/v3`（v2 字面量不回写）。选择在 `_select_facts_for_identity` 控制分支内做**确定性日期选择**：同事实合格 `date_range`（复用现有 time_operand 机器与部分日期区间算法）取最新；并列、部分日期不可比、冲突组成员 → 显式 unresolved 原因（如 `latest_selection_ambiguous`），不取第一条、不默认最新；被替代观察保留审计不删除。语义原子经关系选择后同样按合格日期取一，之后按 single 路径（含 scope 见证要求）求值。方案未声明“以最新为准”时维持 unresolved——与 §17.1“不自行规定总取最新值”一致。

### 5. 是否需要新增模型核实步骤

**不需要。** S1/S4 是纯消费端（证据已在 `proposition-evidence/v3` 双读中产出并双路一致校验）；S2/S3 只需扩展现有解构步骤的模式枚举与提示，日期选择由确定性代码完成。若为“范围见证”另立候选/核实任务：它与命题核实读同一冻结输入、同一批配对、同一 locator 摘录，不产生任何患者侧新信息，只重复双读成本、新增回执链与评测清单，且违背 §17.1.1“不新增另一套调度器”。唯一可能需要新模型能力的是“partial 的结构化子项列举”，本方案明确推迟（收益低、合同+提示+评测成本高）。

### 6. 决策点与有界问题（需 Codex 裁决）

- **Q1（最高影响）**：优先级②中“范围完整见证胜过其他记录的 UNKNOWN”是唯一有实质临床影响的语义选择——一条双读核实的范围级总结陈述，是否压过一条未能核实的个体记录？我的推荐：是（加 witness-conflict 与决胜反例护栏），但请 Codex 明确裁决并在隔离评测中放“总结陈述 vs 过期/矛盾个体记录”双向反例。安全临时路径：不做②，仅做 S4 报告增强（保守但可先行）。
- **Q2**：第一段版本化按计算 v9 + evaluator v13、不触碰提示与消费算法，是否符合“新语义须评测批准后采信”的接入边界（我的理解：计算层变更仍需隔离评测 + 采用授权，只是不需重跑双读）？
- **Q3**：S2 采用“结构化成员原子”而非政策级 finite-set 字段，是否接受？（我推荐前者：零合同变更、缺项天然可枚举；代价是依赖解构粒度纪律，需评测覆盖“一句话枚举三项检查”必须拆三原子的反例。）

### 7. 不确定性声明

以上均为源码级审阅结论与设计建议，未运行任何验证；S1 见证语义、S3 选择规则的最终采信须按项目纪律经隔离评测与用户采用决定。报告不构成临床、监管或视觉验收。
