# Conference Participant Output: phase5-slice58-cross-section-controls-20260824 - general_pi_qwen38

## Boundary Check
- 工作区绑定内独立审查完成，未修改源文件，未读取 `~/.codex/AGENTS.md` 或 `~/.hermes/SOUL.md`，未触及 `.worktrees/phase5-clinical-facts-profile` 外的生产方案/受试者资料。仅读取 `context/` 授权上下文及工作树内合同/构建器/门禁。
- 输出为会商建议，非已验收产品事实；不执行最终视觉/临床/监管验收；Codex 保留终裁。
- 工具启用策略：定向 `read/grep` 求证合同与实现边界，未发起广度探索或联网搜索；初裁“无链接执行包”属实，审查可独立进行。

## Independent Work Product

### 0. 最高优先级异议：`流程表 == 全部额外控制点` 假设不可成立
当前 `build_required_procedure_catalog()` 的确定性假设是闭合的：
- 输入仅为 `StructureBlock(kind==TABLE)` 根，`table_cols/table_rows` 元数据与 `StructureBlock` cell 拆分（`app/protocols/procedure_catalog.py:1078-1122`）。
- 必须满足 `_table_looks_like_flow()` 的 `X/(X)` 标记矩阵与 `first_mark_row`，且有“访视型表头”（`_derive_visit_stage / _header_projection`）。
- `_is_non_enrollment_operation()` 主动丢弃 `随机化操作/研究治疗给药/访视后勤/给药后安全性采集`。
- 去重键 `phase+root+visit.stage+normalized_header+row+col`，身份 `procedure:sha256(CATALOG_BUILDER_VERSION,snapshot,phase,root,row,col,stage,header,label,refs)`。

`app/protocols/deconstruction_service.py:503-545` 与 `app/domain/contracts/agent_io.py:163-187` 进一步将 `allowed_source_span_ids` 冻结为 `parent_catalog ∪ required_procedure_catalog` 的并集并逐级校验 `catalog_spans ⊆ allowed`、`material_ids == allowed`。

**结论**：正文中以段落/列表/脚注出现的禁/限用药表、洗脱期、合并用药章节、疗效/安全阈值、安全窗、评分必做、例外与研究者判断，**必然不在** `required_procedures` 中。若 Phase 5.8 仅复用该目录，基线前审核将系统性漏检洗脱与禁用暴露，导致 II 期/III 期最易发生方案偏离的入排控制点失控。该假设必须显式推翻，不得作为发布完整性依据。

---

### 1. 三类一等对象的领域模型裁决

| 目录 | 权威来源 | 冻结单位 | 典型义务 | 现状 |
|---|---|---|---|---|
| **官方 IN/EX 父规则** | `EligibilitySection` 的 `OfficialParentRuleRange`，编号 `IN-XX/EX-XX` 正则校验 | `CatalogKind.OFFICIAL_PARENT_RULES` / `CatalogItemKind.PARENT_RULE`，`official_code` 必填，`review_stage==None` | 入排判定主规则 | 已冻结 `freeze_official_parent_rules`，门禁强约束 |
| **研究流程必做操作** | 研究流程表 `X/(X)` 访视矩阵 | `CatalogKind.REQUIRED_PROCEDURES` / `REQUIRED_PROCEDURE`，`visit_instance`+`review_stage` 必填 | 审核节点“应做”核对 | 已冻结，但仅覆盖访视矩阵 |
| **全文方案审核控制点** | 全文跨章节文本（入排、合并用药/治疗、检查评估、研究治疗、时间窗/例外脚注、修订案） | **新增 `CatalogKind` 一等对象**（建议命名 `PROTOCOL_REVIEW_CONTROLS` 或 `ENROLLMENT_CONTROLS`，待 Codex 定名），新增 `CatalogItemKind.PROTOCOL_CONTROL` | 禁止暴露/应做核对/需满足条件 三形态 | **缺口**：无合同、无构建器、无 Agent 输入、无门禁 |

**裁决**：三类必须分属三份冻结目录，三种身份命名空间隔离。三类在 `ProtocolDeconstructionInput` 中并列为 `parent_rule_catalog / required_procedure_catalog / review_control_catalog`，在 `RuleSet`/`Rule` 层可统一投影但编号前缀隔离（`IN-XX / EX-XX / REQ-XX / CTRL-XX`）。**禁止**将第三类伪装为 `EX-YY` 子项或改写官方编号连续性，`deconstruction_gate` 已对“修改官方编号和数量”设偿：`official_code` 唯一性/`CatalogKind` 校验应保持。

#### 1.1 为什么不能“扩展 required_procedures”
| 维度 | 扩展现有目录 | 新建独立目录（推荐） |
|---|---|---|
| 身份 | 访视列+行号为键，无访视的正文控制点需伪造 `visit_instance`，污染“同一操作在筛选与基线各一个实例”的语义（`procedure_catalog.py:1130-1204` 注释） | 独立键：`snapshot+phase+canonical_anchor+obligation_kind+target+time_quantity+source_span_ids有序集`，无访视项天然表达 |
| 去重/冲突 | 结构去重无法识别“同一药物在合并用药章与入排章的两段描述为同一控制”；语义重复会被当两条 `X` 操作 | 语义归一化键可区分完全重复/补充/冲突 |
| 审核节点 | 强制 `review_stage!=None` 且来自列头；“研究期间始终禁止”类持续性限制无法映射 | `due_stage` 可为单节点或 `persistent+enrollment_gating_nodes` 数组，基线前各节点均需校验 |
| 时间锚点 | 无 `TimeConstraint`/`ProspectiveWindow`，只能靠标签文本 | 每控制点携带 `TimeConstraint {anchor_type, direction, window, upper_bound}`（复用 `rules.py:TimeConstraint`） |
| 来源闭包 | 复用表格 `source_ref` 合并逻辑，会误合跨表同名操作 | 按 `formal_source_span_ids` 闭包，`allowed_source_span_ids` 为三目录并集 |
| 门禁 | 12 项门禁中 `flow_table_missing/empty` 语义被稀释 | 可新增 3 项独立检查而不削弱既有 12 项 |
| 风险 | 上游 `deconstruction_service._validate_catalog_sources` 与 `agent_io.validate_frozen_scope` 的硬校验需放宽，回归面广 | 新增分支隔离，旧冻结目录哈希与已发布 `ProtocolAuthorityRecord` 不受影响 |

**建议**：新建独立目录，`FrozenProtocolCatalog.catalog_kind` 枚举新增一项；`FingerprintCatalogItem.kind` 新增 `PROTOCOL_CONTROL`；`Rule.kind` 新增 `PROTOCOL_CONTROL`（或复用 `REQUIRED_PROCEDURE` 但需强注释隔离）；`Rule.official_code` 正则扩展为 `^(IN|EX|REQ|CTRL)-\d{2}$` 并新增 `CTRL` 前缀，避免与 `REQ` 混同。

### 2. 跨章节控制点范围界定（确定性可审计清单）

**纳入**（需冻结且进入审核）：
- 禁/限用药、合并治疗、既往治疗的禁用/限制清单、洗脱期/清洗期（含“末次给药距随机≥N周/月”）、剂量/频次限制。
- 合并用药/治疗章节中“研究期间禁用/慎用”的基线前适用子集（如活疫苗、免疫抑制剂），需按 `PhaseScope` 过滤。
- 必做评估/评分/检查：正文描述的“随机前 N 天内必须完成 X 评估/检验/评分（含复测规则）”且流程表未标或标注不一致的。
- 疗效/安全阈值、评分阈值、实验室阈值在正文中的基线前适用形态（含“若异常需复查至满足阈值”）。
- 过程性限制：随机/基线前必须完成的知情、洗脱、导入依从性、剂型转换等。
- 例外、豁免、研究者判断必要条件、以及修订案对上述任一的增删。

**排除**（不得纳入基线前审核控制点目录）：
- 治疗期给药后操作、`_EXPLICIT_POST_BASELINE_RE / _POST_BASELINE_RE` 命中的随访/给药后安全性采集（`procedure_catalog.py:333-352` 已有判定，需复用）。
- 纯物流/访视管理（`_VISIT_LOGISTICS_RE`）与研究治疗给药动作本身。
- 仅在讨论/背景章节出现且无“必须/禁止/不得/要求/禁用/洗脱”义务词的描述性文字。

**关键原则**：正文控制点与官方 IN/EX 是**引用关系而非包含关系**。`IN-03` 正文中提“4 周洗脱”不得被计数为第二个 `IN-03`，而是 `CTRL-NN` 对 `IN-03` 组件的 `EvidenceRequirement`/`FactRuleLink` 关联补充。

### 3. 单个正式控制点的必备结构化形态（冻结后可直接审阅）

每个发布态控制点必须可回答以下 8 字段，缺一不可，未命名即 `unknown/blocked` 不得猜测：

```
ReviewControl {
  control_id:      "control:<sha256>" // 系统生成，不接受 Agent 自编
  kind:            do | condition | prohibition  // 义务形态，禁止压为自由文本
  review_nodes:    ReviewStage[]  // 预筛/筛选/导入/基线；持续性限制为 [screening, run_in, baseline] 且标记 persistent
  action:          { verb: "核对|完成|禁止暴露|取得结果", target: "药物/检查/评分/治疗" }
  condition:       { comparator, value, unit }?   // 仅 condition 形态
  prohibition:     { scope: "exposure|event", targets: string[], negated: true }?
  time:            TimeConstraint? | ProspectiveWindow? | OccurrenceWindow?
                   // 锚点枚举复用 rules.py: AnchorType/ProtocolPeriod + TimeDirection
                   // _must_ 含 explicit anchor；“X 周内”未写锚点 → anchor_unknown 阻断发布
  exception:       RuleExpression?  // 同 DNF v1 形态，触发/例外分离
  min_evidence:    { fact_type, required_source_types[], requires_contemporaneous_objective_source bool, source_validity_window TimeQuantity? }
  judgment_required: bool // 研究者判断必要条件
  source_span_ids: tuple[str,...]  // ≥1，且 ⊆ formal_source_span_ids，来源闭包成员
  provenance:      { source_refs, block_order, page_refs }
}
```

映射到现存合同：
- `kind==do` → 生成 `EvidenceRequirement(procedure_catalog_item_id==control_id, due_stage==review_nodes[0])`；UI 落 `required_procedure_not_done` 缺口。
- `kind==condition/prohibition` → 生成 `RuleComponent(expression, exception_expression, evidence_requirements[])`，`TimeConstraint` 复用 `rules.py:41-122` 的 `anchor_type/time_direction/window`；`prohibition` 形态在 DNF 中表现为带 `Comparator.EXISTS` 否定或 `NOT`  wrapping，门禁已有 `_source_supports_predicate_negation` 可复用。
- `requires_contemporaneous_objective_source` 与 `source_validity_window` 复用 `rules.py:EvidenceRequirement` 已有字段，直接影响 `provenance_followup` vs 阻断性 `historical_source_unavailable` 的区分。

**反模式封堵**：
- 禁止把“应做/条件/禁止”压成一段 `description` 自由文本；`EvidenceRequirement.description` 仅为展示，机器可审字段必须结构化。
- 禁止把“近 4 周”自动锚到“随机”；必须由原文锚词（`_BASELINE_RE/_SCREENING_RE/_RUN_IN_RE`）或显式幅度分支决定，否则进入 `controls_with_unresolved_anchor` 人工核对队列。
- 禁止把治疗期普通操作误纳入基线前：复用 `procedure_catalog._derive_visit_stage` 的 `POST_BASELINE` 拒绝逻辑，对正文控制点做 `stage==post_baseline → exclude_from_enrollment_gating` 过滤。

### 4. 同一控制要求的多章节补充/重复/冲突处置

| 关系 | 判定条件（确定性优先） | 冻结行为 | 门禁 |
|---|---|---|---|
| **完全重复** | 归一化靶点（`lower+去标点+同义词表小集合`）+ 锚点 + `TimeQuantity(value,unit)` + `Comparator` 完全等价，且来源均为正式要求 | 合并为 1 个 `control_id`，`source_span_ids` 取并集（去重保序），审计保留多源 | 通过；`Gate` 记录 `duplicate_merged` 非阻断 |
| **相互补充** | 同靶点不同时间窗/不同例外/不同最低证据等级，如流程表脚注“2 周” vs 合并用药章“4 周” | **不合并**，形成两条控制点，进入 `supplement_pair` 关联；最严窗不自动覆盖较宽窗 | 阻断发布，提示“同靶点时间窗补充不一致，需医学确认取并集或以修订案为准” |
| **实质冲突** | 同靶点一处 `prohibition` 另一处显式 `allow`，或阈值方向相反/人群互斥 | 两条均保留，标记 `conflict_group`，关联 `InterpretationSource` | **阻断发布**，与 `deconstruction_gate` 的 `interpretation_conflict`/`source_conflict` 同级 |
| **IN/EX 与正文重复** | 控制点靶点与某 `IN/EX` 组件谓词重叠（共用 `predicate.binds_obligation` 命中） | 控制点不改 IN/EX 数量，`FactRuleLink` 指向该组件作补充，不新增 `official_code` | 通过但需 `cross_catalog_reference` 校验：正文控制点不得单独声称等价于新增 EX/IN |

相似文本绝不直接合并；合并键必须是归一化语义键 + 锚点/时间量化，`_normalized()`/`_longest_common_run()` 仅为辅助证据，非合并依据。

### 5. 确定性候选发现 / Agent 语义解构 / 人工核对 / 发布门禁的分层边界

**阶段 1 - 确定性候选池（不直接成正式规则）**：
- 输入：`PhaseProjection + SectionIndex + ProtocolSourceSpan`（复用 `catalogs.py:build_section_index`）。
- 产出：`ControlCandidate { span_ids, excerpt, candidate_kind, anchor_hint, time_hint, targets_hint, obligation_hint }`。
- 规则：仅基于通用临床义务词表（`禁用/禁止/不得/避免/慎用/洗脱/清洗/排除/要求完成/必须取得`）与 `_VISIT_OR_DATE_RE/_BASELINE_RE/_SCREENING_RE` 等锚点词表做候选召回；**不编码 D001/MG 药名**；候选必须携带 ≥1 `formal_source_span_id`，否则丢弃。
- 约束：候选池大小不决定发布完整性，候选遗漏由完整性校验捕获。

**阶段 2 - 冻结目录**：
- 将去重后的候选按 `canoncial_key` 生成候选目录快照，写入 `FrozenProtocolCatalog(catalog_kind==PROTOCOL_REVIEW_CONTROLS)` 预冻结；此时 `control_id` 仍为候选身份，未发布。

**阶段 3 - Agent 水合（唯一语义生产者）**：
- `ProtocolDeconstructionInput` 新增 `review_control_catalog` 与 `review_control_source_span_ids`；`build_protocol_deconstruction_prompt()` 将候选控制点作为**可引用来源块**而非自由文本注入；Agent 仅能输出 `dnf-v1` 形态的 `Control`（复用 `protocol_deconstructor.py: _wire_*` 的 compact wire 约束：`MAX_GROUPS/ATOMS` 同步适用）。
- Agent 不得自编 `control_id/span_id`；`_system_predicate_id` 保持系统生成；`source_clauses` 保序入哈希（`dnf-v1` 已修复）。

**阶段 4 - 人工核对**：
- 在 `ProtocolAuthorityConfirmation` 中对每个控制点做 `formal_requirement vs clarification_only` 鉴别（复用 `enums.InterpretationAuthority`），未决锚点进入 `controls_with_unresolved_anchor` 待办，不阻断 IN/EX 发布但阻断该控制点发布。

**阶段 5 - 发布门禁（`deconstruction_gate` 扩展）**：
现有 12 项门禁保持不变，新增 3 项（建议增至 15 项，版本号升级）：
1. `review_control_source_closure`：每个控制点 `source_span_ids ⊆ formal_source_span_ids` 且 `allowed_source_span_ids == union(3 catalogs) ∪ materials`。
2. `review_control_anchor_resolved`：`kind==prohibition/condition` 且涉及时窗的控制点必须有显式 `TimeConstraint.anchor_type`，`unknown` 锚点阻断发布。
3. `review_control_duplicate_conflict`：跨章节重复/补充/冲突按第 4 节矩阵处置，未解决的 `supplement/conflict` 阻断发布。

**阶段 6 - 发布**：`RuleSet + WorkflowStage + ProcedureEvidenceRequirement + ReviewControl` 原子写入 `ProtocolAuthorityRecord`，`catalog_sha256` 按 `protocol_ingestion.py:254-261` 同款 `canonical_hash` 计算，`frozen_by` 包含新 builder 版本 `review-controls/v1`。

### 6. 稳定身份、来源闭包、去重/冲突、完整性与发布停止条件

- **稳定身份**：`control_id = "control:" + sha256(snapshot_id, phase, obligation_kind, canonical_target_key, anchor_type, direction, time_quantity, exception_canonical_key, sorted_source_span_ids_without_order_loss?)`。注意 `source_clauses` 入身份时保序（`dnf-v1` 回归：`source_clauses` 排序缺陷已修），但 `source_span_ids` 去重保序不排序，跨修订可比对。
- **来源闭包**：复用 `deconstruction_gate` 已有 `catalog_source_ids` 与 `formal_source_span_ids` 子集校验；`procedure_catalog._validate_phase_context` 的期别投影一致性同样适用。
- **去重/冲突**：见第 4 节矩阵；`_canonical_wire_atom_key/_canonical_wire_group_key` 的归一化思想可移植到控制点 `target_key` 生成。
- **完整性门禁**：
  - 必检章节覆盖率：入排、合并用药/治疗、研究治疗、检查/评估、流程表脚注、修订案；任一章节未产出任何控制点且该章节含义务词 → `coverage_incomplete` 阻断（类似 `tests/v2` 中 `flow_table_missing/empty`）。
  - 页覆盖 `ExtractionCoverage.tracked_change_count / 页清单闭合` 从 Phase 3 继承：遗漏整页 → 阻断。
  - 期别投影：`PhaseScope` 非选中期别的表格/段落不得进入基线前控制点目录，`_selected_scope/_select_phase_rules` 逻辑复用。
- **发布停止条件**（Codex `plans/...: 7.1` 的裁决）：任一门禁失败 → 不发布 `RuleModelRevision`；原文理解分歧走 `revise_protocol_draft_from_feedback` 局部修复，同会话限次 `repair`（`protocol_deconstructor.py:_select_repair_rule_codes` 轮询语义每条受影响父规则一次）；仍失败则停在草稿，不生成“空控制点集”的虚假通过。

### 7. Phase 5.8 增量实施顺序（不写死 D001/MG 语义）

**5.8a 合同与枚举**（无模型、无真实文件）：
- 新增 `CatalogKind.PROTOCOL_REVIEW_CONTROLS`、`CatalogItemKind.PROTOCOL_CONTROL`、`RuleKind.PROTOCOL_CONTROL`（或 `RuleKind.REVIEW_CONTROL`）、`Rule.official_code` 的 `CTRL` 前缀；`FrozenCatalogItem` 对控制点放开 `visit_instance` 非必填、要求 `review_nodes` 非空；新增 `TimeConstraint` 复用不变。

**5.8b 确定性构建器**：
- 新建 `app/protocols/review_control_catalog.py`：`build_review_control_catalog(blocks, projection, spans, selected_phase, snapshot_id)`，复用 `section_index/formal_source_span_ids/phase_projection` 管线；产出候选级冻结目录；聚焦测试覆盖：期别过滤、锚点未命名阻断、治疗期排除、多源合并、多表同名去重。

**5.8c 输入与传输**：
- 扩展 `ProtocolDeconstructionInputAssembler.assemble()` 产出第三目录并校验三目录并集闭包；扩展 `build_protocol_deconstruction_prompt()` 注入控制点候选块；扩展 `protocol_output_response_format` 的 compact wire schema 支持 `controls[]`；保持 `dnf-v1` 无引用约束与 `MAX_*` 保护（复杂度保护值待真实规则规模校准）。

**5.8d 门禁与可视化底稿**：
- 扩展 `deconstruction_gate` 至 15 项，版本 `2026-08-24.3`；新增 3 项门禁的聚焦测试；Patient Profile 泳道中控制点独立一泳道或并入“证据冲突与资料质量”但保持可追溯到 `control_id` 与多源定位（复用 Phase 5 的 `bbox` 真实定位门禁）。

**5.8e 真实校准与发布阻断验证**：
- 用新 `dnf-v1` 对 D001 II 与 MG-K10-SAR III 各起新隔离项目（执行 `implement.md:5.8` 已写明的“原始输入在隔离目录创建新架构测试项目”），逐项人工比对 IN/EX、流程必做项、跨章节控制点；前两路为合同/门禁校准，不进入独立测试者；通过后才开放 3 路独立测试者试用。

**停止条件**：
- 任一新增门禁回归失败、或任一隔离项目出现锚点猜测/重复计数/治疗期误纳入/源外引用 → 回到 5.8b/c 合同根因修复，不以“先跳过该控制点”继续推进。

---

## Evidence And Assumptions

**直接证据（已读）**：
- `app/protocols/procedure_catalog.py:CATALOG_BUILDER_VERSION="required-procedures/v1"`, `build_required_procedure_catalog` 的 `TABLE` 根遍历与 `X/(X)` 要求（`1078-1122`），`_derive_visit_stage` 的锚点优先级与 `POST_BASELINE` 拒绝（`333-352`），`_is_non_enrollment_operation` 的 3 类丢弃（`429-452`），去重键与身份生成（`1130-1204`），合同哈希 `canonical_hash`（`1227-1231`）。
- `app/protocols/catalogs.py:CATALOG_BUILDER_VERSION="official-parent-rules/v1"`, `_OFFICIAL_CODE_RE="^(IN|EX)-\d+"`, `freeze_official_parent_rules` 的编号连续性与期别过滤。
- `app/domain/contracts/protocol_ingestion.py:FrozenCatalogItem` 字段约束（`219-232` 含 `visit_instance/review_stage` 互斥校验，`234-285` 的 `catalog_kind` 分支校验与 `catalog_sha256` 自哈希）。
- `app/domain/contracts/enums.py:CatalogKind` 仅 `OFFICIAL_PARENT_RULES/REQUIRED_PROCEDURES`（`310-314`），`ReviewStage` 4 枚举，`RuleKind` 3 枚举，`Rule.official_code pattern IN|EX|REQ`（`rules.py:283`）。
- `app/protocols/deconstruction_service.py:ProtocolDeconstructionInputAssembler.assemble` 的双目录冻结→ `_validate_catalog_sources` → `allowed_source_span_ids == union` → `_build_source_materials` 闭包（`503-585`），失败码 `catalog_item_without_formal_source/catalog_material_coverage`。
- `app/domain/contracts/agent_io.py:ProtocolDeconstructionInput.validate_frozen_scope` 的 `allowed==material_ids`/`catalog_spans ⊆ allowed` 强校验（`148-188`）。
- `app/domain/contracts/rules.py:TimeConstraint/OccurrenceWindow/ProspectiveWindow/ProspectivePeriod`, `EvidenceRequirement` 的 `procedure_catalog_item_id xor rule_component_id` 与 `due_stage/source_validity_window`（`250-268`），`Rule/Ruleset` 的 `official_code` 前缀与 `kind` 一致性（`281-335`）。
- `app/agents/protocol_deconstructor.py:dnf-v1` 紧凑无引用 schema、 `DNF_WIRE_MAX_*` 保护（`76-83`）、`uses_compact_wire_contract`、`source_clauses` 保序修复（`implement.md:dnf-v1` 回顾与 `protocol_deconstructor` 注释）。
- `app/protocols/deconstruction_gate.py:DECONSTRUCTION_GATE_VERSION`、`CHECK_NAMES` 12 项与 `ProtocolGateIssue.repair_scope` 机制、`GateOutcome` 三态。
- `plans/codex_main_venue_phase5-slice58-cross-section-controls-20260824.md:17-18` 的“只遍历表格根、只认访视列 X 标记、无独立全文控制点对象”已知缺口。
- `.trellis/tasks/08-22-phase5-clinical-facts-profile/implement.md:5.8` 的“隔离目录创建 D001 II/MG-K10-SAR III 新项目→Codex逐事件核对→三路独立测试者”门槛与 `CHECKPOINT_20260824_DNF_V1_IMPLEMENTATION_ACCEPTED.md` 的“`dnf-v1` 候选与修订共用形状、组内且组间或、原子否定、系统生成稳定身份”已验收范围。

**推断（标记）**：
- [INFERENCE] D001/MG 真实方案的洗脱期与禁用药表大部分位于段落/列表而非流程表，基于行业 II/III 期方案通常结构与当前构建器仅遍历表格根的事实联合推断，未读真实文件不视为确证。
- [INFERENCE] 最优 `CTRL` 前缀与 `ProtocolKind` 命名需 Codex 最终定版，此处为工程建议，非既有合同。

## Risks, Gaps, And Verification Needs

**High severity**
1. **“流程表即全部”导致的假完整**：若 5.8 延续双目录发布，管理层与申办方将获得“流程表已全覆盖”的错误安全感，基线前洗脱违规与禁用暴露漏审概率高。验证：任选 D001 一章“合并用药”段落做人工抽检——能找到 ≥1 条带时间锚点的禁用/洗脱语句且不在 `required_procedures` 中即证伪。
2. **未命名时间锚点猜测**：正文中“4 周内”未写锚点，模型易默认锚到“随机”而实际应为“筛选开始”或“末次给药”。已在 `TimeConstraint` 合同中 `anchor_type` 必填，但门禁尚未对控制点强制 `anchor_unknown → BLOCKED`。验证：构造“停用生物制剂至少 4 周”无锚点句的候选，断言门禁拒绝并进入人工待办。
3. **IN/EX 与正文控制点重复计数**：把正文中对 IN/EX 的复述计为新增 EX，将破坏官方编号连续性与 `Gate` 的 `official_code` 唯一性校验，且使覆盖率虚高。验证：对 `IN-xx` 溯源片段与某 `CTRL-yy` 的谓词做 `_predicate_binds_obligation` 双重绑定测试，确认仅产生一条 `Rule` 的额外 `EvidenceRequirement` 而非两条 `Rule`。

**Medium severity**
4. **治疗期操作污染基线前审核**：`_POST_BASELINE_RE` 仅覆盖访视列头词，正文中的“治疗期每 2 周给药”若锚点识别不准会被误冻为筛选控制点。验证：构造含“治疗期”“随访期”的正文控制点候选，断言被 `post_baseline` 过滤器排除。
5. **去重误合补充与冲突**：以文本相似度合并会把“筛选期禁用 2 周”与“合并用药章 4 周洗脱”误合为一条，导致最严窗丢失。验证：对同靶点两条不同 `TimeQuantity` 的候选断言合并键不等且门禁报 `supplement_pair`。
6. **来源闭包旁路**：若 Agent 被允许引用不在 `allowed_source_span_ids` 中的段落，`Gate` 现有 `catalog_source_ids ⊆ allowed` 校验未覆盖第三目录时将失效。验证：新增第三目录后对 `allowed` 并集做 determinstic 快照对比测试。
7. **复杂度保护校准缺失**：`dnf-v1` 的 `MAX_GROUPS/ATOMS` 暂为保护性估计（`protocol_deconstructor.py:76-83` 注释“仍须由 D001 II 与 MG-K10-SAR III 真实规则规模校准”），跨章节控制点加入后真实规模将上升，未校准前易触发 `complexity_rejected` 误阻断或放宽后失控。验证：用 D001 全文控制点真实数量做分布统计后定阈值。

**Low but non-negligible**
8. **修订案权威边界**：修订案可改变标准，解释材料不可（`docs/REARCHITECTURE_FINAL_DESIGN` 与 `enums.InterpretationAuthority`）。若控制点来源未区分 `amendment` vs `medical_interpretation`，解释函中的“口头放宽”会被误作正式控制点。验证：`ProtocolSourceSpan` 的来源类型标注测试。

**Verification asks already embedded in product**
- 所有控制点落地后必须满足 `implement.md:5.8` 的三段式验证：聚焦测试→层回归→D001 II/MG-K10-SAR III 隔离项目逐项人工比对（含流程必做项与跨章节控制点逐条对照）；通过后才启动 3 路独立测试者；浏览器定位真实 `bbox` 才画框（`P5-AC02`）与 `compileall/git diff --check` 通过为硬门槛。

## Recommended Next Step

**对 Codex 主会场的显式建议**：

1. **采纳三目录一等对象 + 独立 `CTRL` 命名空间**（第 1 节），拒绝“扩展 required_procedures”路线。由 Codex 在 5.8a 中定版枚举命名（`PROTOCOL_REVIEW_CONTROLS` vs `ENROLLMENT_CONTROLS`，`CTRL` 前缀是否与既有 `REQ` 并列）。

2. **按 5.8a→5.8e 切片顺序执行**，每切片聚焦测试与回归双门槛，任一切片未通过即阻断下一切片，不进入独立测试者。

3. **冻结“8 字段控制点”合同**（第 3 节）与第 4 节重复/补充/冲突矩阵，作为 `review_control_catalog` 与 `deconstruction_gate` 的合同用例来源。

4. **立即将“流程表≠全部”写入发布门禁的阻断理由**，在 UI 中对“流程表必做项”与“方案审核控制点”做分泳道展示，避免用户误认完整。

**需 Codex 裁决的有界问题（阻塞后续合同细节，需同会话答复；答复前走安全 provisional path）**：

1. **命名与枚举**：`CatalogKind` 第三项与 `RuleKind` 第四项的正式命名是否为 `PROTOCOL_REVIEW_CONTROLS / PROTOCOL_CONTROL` 且 `Rule.official_code` 扩展为 `CTRL-\d{2}`？若否，现阶段以 `PROTOCOL_REVIEW_CONTROLS` 为 provisional 命名进入 5.8a，待确认后一次性重命名（枚举值变更需迁移，但未发布前无历史数据）。

2. **持续性限制的节点归属**：形如“研究期间始终禁止 X”的正文控制点，是否冻结为 `review_nodes=[SCREENING,RUN_IN,BASELINE]` 且标记 `persistent=true`，由每节点审核函数重复校验？provisional 采用此方案，避免单节点遗漏。

3. **发布阻断粒度**：含 `anchor_unknown` 或 `supplement_pair` 未决的 `CTRL` 是否阻断整份 `RuleModelRevision` 发布，还是仅阻断该 `CTRL` 子集发布而 IN/EX 仍可发布？provisional 采用“整包阻断”（与修订案权威边界一致），因部分阻断易造成申办方对“已发布即完整”的误判；若 Codex 倾向部分发布，需同步设计 UI 的“部分可用/待确认 n 项”非阻断态。

4. **修订案 vs 解释材料的权威标记**：`ProtocolSourceSpan` 是否已携带 `InterpretationSourceType/InterpretationAuthority` 可供控制点构建器直接消费？若缺失，provisional 在 5.8b 先按 `source_span_id` 关联的 `DocumentPart/Amendment` 标签做近似过滤，后续由来源元数据完善。

**Provisional path if unanswered**：按上述 provisional 决策完成 5.8a 合同草案与 5.8b 候选构建器的确定性骨架，不调用真实 oMLX，不进入 D001/MG 隔离项目，等待 Codex 对 4 个命名/语义问题同会话确认后再冻结 wire schema 与门禁版本。
