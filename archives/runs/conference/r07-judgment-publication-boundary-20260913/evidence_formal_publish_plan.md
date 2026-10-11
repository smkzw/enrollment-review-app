继续只读设计审阅：先读指定设计文档与当前冻结计算/发布合同，再回答最小可建的 ReviewRun 扩展路径。接着读冻结计算、装配器和现有发布门禁的实现，确认能安全扩展的最小范围。# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读设计审阅：如何在不伪造 AgentCall/旧事实、也不绕过谓词证明的前提下，把现有 `ReviewRun → FinalAssessment → ActionRequest` 接到可发布的 `review/v2`。未改代码、未跑测试、未读库、未调模型。不是临床接受。

### 结论（先答问题）

**可以做最小完整扩展，但不要去改 `publish_assessment` 成版本联合体。** 现有发布闭包焊死了 v1：`AgentCall` + `AssessmentCandidate`（观察必须逐字段复述求值）+ `ReviewContextSnapshot` + `EvidenceNormalizationCandidate` + `require_registered_review_scope` 的 legacy `evidence_snapshot`（`assessment.py:439-515,521-547`；`scope.py:45-76,104-110`）。给 V2 伪造这些对象，就是在绕过来源/模型证明。

**应加一个小的 V2 发布适配器，复用同一判定矩阵，不复制求值器/表/队列。** 输入用已装配的 `ReviewContextSnapshotV2`；求值走 `evaluate_bound_component_experiment`（显式事实清单，空清单不回退类型匹配）；缺口/结论/待办走现有 `derive_gate_gap_types`、`derive_component_decision`、`validate_decision_gap_matrix`、`derive_assessment_blocking_level`、`ACTION_CONTENT`。落库仍是现有 `review_runs` / `final_assessments` / `action_requests` 的 `review/v2` 行。

**可以在正式审核里保留未知/未核实谓词及其精确原因，同时对已批准清单上的输入做布尔/日期/单位计算；实验绑定不得自动采信。** 当前隔离入口已证明消费方式（`expression.py:568-608`），`accepted=false`、不注册。在对应算法获准前，清单只能是空的：确定性计算仍运行，但不会从大类或精确 `fact_type` 放行符合/排除。完整供给范围检索未见书面判断 → `PROFESSIONAL_JUDGMENT` + 研究者待办，不是用户确认环。不完整检索 → `OBSERVATION_UNVERIFIED`，与前者分开。禁止把 `calculate_frozen_review` 的类别候选当证明发布。全未知正式记录可以存在，但必须呈现为「本次冻结的缺口报告」，不得写成完整临床评估或可入组。

### 已核实的源码事实

1. **v1 发布不能吃 V2 输入。** `publish_assessment` 要求 `ReviewContextSnapshot`、证据候选、双侧 AgentCall，并用 `evaluate_component`（默认可走类型别名）重算（`assessment.py:439-447,596-632`）。`AssessmentPublication` 无 V2 字段（`52-65`）。`validate_assessment_candidate` 要求候选观察与求值逐字段一致（`369-435`）。没有模型调用就无法诚实满足。

2. **冻结计算明确不是发布。** `frozen_review_calculation.py:1,28,60-65` 写入 `_component_candidate_types`（把组件全部 `fact_type` 铺到每个谓词，`eligibility_review_projection.py:636-645`）。注释写明只为计算对等，不是语义证明。把它接到发布会静默改变临床语义。

3. **唯一共享计算核已经存在。** `component_review.py:25-44` 调用 `evaluate_component` + `derive_gate_gap_types` + `derive_component_decision`。缺口还可并入 `source_gaps`。检索四态已在 `_summary_gaps`（`395-460`）：无摘要/候选/不完整 → `OBSERVATION_UNVERIFIED`；供给页搜完无候选且该要求非 OBSERVED → `PROFESSIONAL_JUDGMENT`；缺文件不被「搜完」覆盖。

4. **未知原因映射会把「未见事实」收成缺记录。** `REASON_GAPS` 有 `professional_judgment_unverified` → `OBSERVATION_UNVERIFIED`，无 `fact_not_observed`（`assessment.py:206-217`）。求值无匹配时普通谓词给 `fact_not_observed`（`expression.py:460-466`）。若缺口集仍空，`derive_gate_gap_types` 加 `RECORD_INCOMPLETE`（`297-307`）。待办文案因此变成「补关键信息」（`policies.py:73-76`），而不是「核对现有资料」。这正是「把每个未知标成缺来源」。

5. **绑定实验入口保持未注册。** `evaluate_bound_component_experiment` 核组件/上下文哈希，要求触发与例外清单完整，空清单合法且不走 alias（`expression.py:454-459,568-597`）。设计 §17.1.1 与计划 T1 写明正式自动采信仍须隔离评测与用户确认。

6. **装配与历史读已经分开「选 latest」和「读冻结」。** 装配只在新建时 `latest_entries_for_authority` 并 `freeze`（含不完整检索，`review_context_assembly.py:28-31,58-64`）。`review_history_service.py` 不重算、不读活动指针、不投影现行条款；条款身份来自冻结 `clause_pack`；行动是当前修订。后续资料更新不改写已存报告。

7. **历史 GET 在资料更新后仍可读（源码路径，未跑库）。** 它核 run/context 身份与冻结修订哈希（`206-242,246-271`），不调用 `FactAuthorityValidator.validate()`（当前活动）。`validate_review_references` 按冻结权威查 locator（`review_reference_validation.py:48-50`），且只在 **新写** assessment 时跑。列表/详情用当前 episode 只核 `project_id`/`subject_id`，不要求当前 `active_*` 仍等于冻结快照。规则修订按 `get_rule_set(id, run.rule_set_revision)` 追加读历史行。

8. **行动指令仍是 v1 形状。** `derive_action_directive` 吃 `EvidenceExpectation` 与 `evidence_span_ids`，产出 `trigger_evidence_span_id`（`policies.py:141-197`）。V2 期望/定位不能原样传入 `publish_action_request`（`actions.py:78-118`）。

### Findings（严重度）

1. **高：把 `calculate_frozen_review` 或无清单的 `evaluate_component` 接到正式发布，会把类别/类型匹配写成已证明结论。**  
   `frozen_review_calculation.py:60-65`；`expression.py:452-459`；设计 17.1「大类 fact_type 不能代替医学语义匹配」。  
   **最小做法：** 发布路径禁止设 `predicate_fact_type_aliases`。谓词一律走 `evaluate_bound_component_experiment`。未获准对应 → 空清单 → `UNKNOWN`。获准前不得发布 `INCLUSION_MET` / `EXCLUSION_NOT_TRIGGERED` 等明确符合态。工作底稿可继续用冻结计算，报告不得当证明。

2. **高：不能靠扩展 `publish_assessment` 的版本联合体做 V2。**  
   `assessment.py:52-65,439-515`；`scope.py:60-76`。联合体仍要 AgentCall、v1 上下文、归一化候选、legacy 快照。伪造它们等于绕过证明。  
   **最小做法：** 新增 `publish_frozen_assessment`（名可再定）适配器：输入 `ReviewContextSnapshotV2` + 冻结 RuleSet 修订 + 绑定清单（现为空）+ 检索缺口；输出现有 `FinalAssessment`/`GateResult`。`GateResult.input_entity_refs` 指向 `context_id`、组件、run，**不要**指向虚构 AgentCall。不要新表、新 JobRunner、新求值器。

3. **中：共享缺口函数会把「未对应」收成「缺记录」，待办对象/动作会错。**  
   `assessment.py:297-307`；`expression.py:460-466`；`policies.py:68-76`。  
   **最小做法：** 不要改全局 `REASON_GAPS`（会改 v1 语义）。V2 适配器在调用矩阵前把 `fact_not_observed` 映射为 `OBSERVATION_UNVERIFIED`，或并入 `source_gaps`。完整供给未见判断继续只用 `_summary_gaps` 的 `PROFESSIONAL_JUDGMENT`。

4. **中：正式记录目前没有逐谓词原因；历史阅读器也读不到。**  
   `FinalAssessment` 只有组件级 `decision`/`gap_types`/`used_fact_ids`（`review.py:249-265`）。精确 `reason_codes` 在 `EvaluationResult` / 候选观察里。`get_run` 不加载 `GateResult`（`review_history_service.py:440-481`）。全未知报告若只显示「暂不能明确」，用户会看成完整评估失败，而不是「这些条件未核实」。  
   **最小做法：** V2 `GateResult` 的 `input_scope_hash` 载荷写入完整 `ComponentEvaluation`（v1 已有类似字段，`assessment.py:668-676`）。历史详情解码该 Gate，按谓词展示 `truth` + `reason_codes`。不必新表。不要为凑旧「观察必须镜像求值」检查而造 `AssessmentCandidate`。

5. **中：`publish_action_request` / `derive_action_directive` 不能直接吃 V2 期望与 locator。**  
   `policies.py:141-197`；`actions.py:83-118`。硬接会空触发定位或类型错误。  
   **最小做法：** 指令文案复用 `ACTION_CONTENT`。V2 分支用 `trigger_locator_id`（评估 `locator_ids` 与期望定位的稳定排序首项），`due_stage` 算法与现函数相同。仍走现有 Action 表与 `validate_decision_gap_matrix`。关闭行动不改历史结论（历史阅读器已如此）。

### 可现在建的安全范围

| 现在可以落库 | 现在不能宣称 |
|---|---|
| 正式 `ReviewRun` + 已装配 V2 上下文（来源核验发生在装配时） | 谓词语义对应、用药分项自动采信 |
| 每个条款一条 `FinalAssessment`：`NOT_DUE` / `NOT_APPLICABLE` / `INDETERMINATE` / `PROFESSIONAL_JUDGMENT` / `CONFLICT` | `INCLUSION_MET` 等明确符合（除非该谓词已有获准清单——当前没有） |
| 完整供给范围未见判断 → PJ + 研究者待办，审核可完成本次 | 用户确认「缺失」；把不完整检索写成未见 |
| 不完整/未跑/有候选检索 → `OBSERVATION_UNVERIFIED` + CRA 核现有资料 | 「全部未知」= 临床评估完成或可入组 |
| 已核实事实的日期/单位/布尔计算，**仅当**该谓词有显式获准清单 | 把 FactRuleLink / `supported_requirement_ids` / 类别匹配当证明 |
| 报告读冻结上下文 + 已存结论 + 行动当前状态 | `claims_complete`；产品模型调用；第二套评估器 |

实验绑定：继续只走隔离入口；发布适配器读「已注册获准清单」，注册表为空则全部空清单。不要把 r4/r5 候选写入正式链。

全未知报告：每个条款仍要有评估行（历史阅读器在 `completed_at` 时要求条款包全覆盖，`466-472`），决策为不确定/需判断/未到期/冲突，并带谓词原因。UI/报告标题必须是正式缺口记录，不是入排结论。

### 版本联合体 vs 适配器

**选适配器。** 联合体要么把 AgentCall 变成可选（削弱 v1 证明），要么为 V2 填空壳（伪造）。适配器共享矩阵与表，发布证明改为：冻结上下文哈希、规则修订哈希、绑定清单哈希（可全空）、检索冻结身份、求值载荷。v1 `publish_assessment` 原样不动。

### 最小实现顺序

1. 发布适配器：禁止 alias；`evaluate_bound_component_experiment` + `_summary_gaps` + 现有 derive_*；空清单；映射 `fact_not_observed` → 未核实（仅 V2 路径）。
2. 写 `FinalAssessment` `review/v2`（locator、V2 快照指针、空 span）和 `GateResult`（含完整 evaluation）。不写 AssessmentCandidate/AgentCall。
3. 按 `gap_types` 写 `ActionRequest`；PJ 用研究者补充文案；未核实用 CRA 核对文案；定位用 locator。
4. 历史详情展示 Gate 内逐谓词原因；行动当前状态分列。装配保持「只在新建选 latest」。
5. 获准对应后：只把已注册清单填进步骤 1，仍无第二求值器。用药分项同样隔离。

代价：获准前正式报告几乎都是缺口/需判断，看起来「没用」。这是正确的。把冻结计算发布出去会好看，但是假评估。

### 历史读与后续资料更新

**可以读。** 阅读器不重跑 `prepare`/`verify_frozen`/`FactAuthorityValidator.validate`，不用现行投影器重建条款。风险是历史规则行被原地改写（追加修订模型下不应发生）或冻结上下文行丢失（已闭失败）。新写 run 仍要求当前活动权威（`repositories.py:445-461`）；这不影响旧报告 GET。

### 观察到的具体缺陷（不是建议新框架）

- 不完整检索已能冻进上下文，但还没有正式发布器消费它；实时投影可以显示缺口，报告不能把实时投影当正式结论（T5 已改历史列表，发布仍缺）。
- `_summary_gaps` 把 `CANDIDATES_PRESENT` 与 `COVERAGE_INCOMPLETE` 同为未核实：符合设计四态，发布时必须原样保留，不得把有候选升级为已核实判断。
- `review_authority` 在 assessment **保存**时用当前 episode 的 project/subject/rule_set 拼冻结 run 指针（`review_reference_validation.py:12-25`）。GET 不跑该函数。未实测「保存后改 project 字段」；身份字段通常稳定。

### Uncertainty

未执行发布事务、未跑历史 GET、未测 0023 库。所有者编译不是功能证据。谓词对应与用药分项仍隔离。本角色不主张临床/监管接受。

### 对实现者的硬边界

不要为了让报告「看起来完整」而发布类别求值。不要把每个 `UNKNOWN` 标成缺来源。不要为确定性 V2 计算伪造 AgentCall。不要在上下文 GET 上重跑检索核验。不要新队列。获准前的正式链是冻结缺口 + 书面判断待办，不是入组证明。
