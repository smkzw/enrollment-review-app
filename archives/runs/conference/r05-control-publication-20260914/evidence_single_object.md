All evidence is gathered. The stage-id space mismatch is confirmed (frozen-source ids `workflow-stage-<hash>` vs published namespaced ids `{rule_set_id}:{revision}:...`). I can now compose the complete report.

# Conference Output: r05-control-publication-20260914 - evidence_single_object

## Output

**结论**：候选→正式控制的验收边界已经存在且足够严格，但当前只用空目录脚手架调用；断点不在门禁，而在(i)无候选→`ProtocolReviewControl` 的确定性晋升步骤、(ii)无持久化与 RuleSet 修订绑定、(iii)四个下游消费者全部只读官方规则。`RuleComponent` 不能忠实表达控制语义，不应压平；最小路径是"平行目录 + 控制侧期望扩展"，而非改造 ClausePack v1。

### 一、现状断点（证据）

- `_execute_gate` 构造 `controls=[]` 的空目录仅作闭包校验，返回 `accepted:true` + `formal_catalog_status:"not_materialized"`（`app/services/protocol_control_execution.py:1635-1710`）；该结果除重放守卫（:942）外无任何消费者。**此 accepted 不能视为发布批准——正确。**
- 验收边界已存在：`validate_protocol_control_publication` 支持非空目录（`app/protocols/protocol_control_gate.py:4397-4570`），`_validate_control`（:4079）强制 5.8b 显式义务 DNF、适用性/触发/义务/例外逐层来源闭包、modality/节点忠实性、专家判断与证据保真等检查；`publish_protocol_control_catalog`（:4573）已声明"门禁是唯一写边界"。生产代码无任何 `ProtocolReviewControl(` 构造点（仅测试）。
- 持久化缺失：`PublishedProtocolControlCatalog` 是纯校验合同（`app/domain/contracts/protocol_controls.py:1680`），无表、无 RuleSet 修订绑定。
- 消费者全部只读官方规则：ClausePack 投影只迭代 `rule_set.rules[].components[]`（`app/projections/clause_pack.py:96-134`）；实时投影 `project_clause_pack(rule_set)`（`app/services/eligibility_review_projection.py:657`）；页审条款包（`app/services/page_review_job_service.py:96`）；资料期望 `_all_requirements` 只收规则组件+流程必做（`app/projections/evidence_expectation_templates.py:39-60`）；正式审核上下文只冻结官方 ClausePack（`app/services/review_context_assembly.py:41-43`）。

### 二、RuleComponent 表达力判定（不能，且有三处硬伤）

1. **义务类型与强度**：`ControlObligationKind` 10 类 × `ControlObligationModality` 3 档（含 recommended/best_effort 非阻断义务）在 `AtomicPredicate`/`RuleExpression` 无对应；只有 REACH_CONDITION/PROHIBIT_* 可勉强映射为谓词，COMPLETE_OR_VERIFY、SCHEDULE_OR_VERIFY_VISIT、SELECT_BASELINE_VALUE、MUST_RECORD、MUST_PROFESSIONAL_ASSESSMENT 是流程义务而非受试者事实谓词。合同还显式禁止 recommended/best_effort 用于禁止类（`protocol_controls.py:200-209`），压平即伪造。
2. **四层 DNF 与条件豁免**：`RuleComponent` 只有 `expression`+`exception_expression`；控制的适用性/触发/义务/例外分层及例外 `waives_trigger_branch_indexes`/`activates_obligation_group_indexes`（:951-966）无法表达。且控制原子是"陈述文本+来源+time_constraint"（`ControlConditionAtom`:908、`ControlObligationAtom`:847），不是可求值谓词——强行转 `exists` 正是 T1 已禁止的"未核实语义用 exists 放行"。
3. **编号与身份**：`Rule.official_code` 与 `ClausePackClause.official_code` 均硬绑 `^(IN|EX|REQ)-\d{2}$`（`rules.py:312`、`clause_pack.py` 合同），控制进入即伪造官方编号，违反 §17.3。控制已有自身稳定身份 `protocol_control_id` + "方案控制 NN" 展示（§17.4 一致）。

**最小合同扩展**（替代压平）：`EvidenceRequirement` 来源三元增加互斥第三支 `protocol_control_id`（现合同 `rules.py:291-297` 强制二选一，控制最低证据两支都不符）；`ReviewContextSnapshotV2` 增加冻结的完整控制目录字段。ClausePack v1 不动。

### 三、最小接线方案（有界编辑计划）

前置（P0，两个已证身份漂移，均为源码级缺陷风险而非臆测）：
- **目标漂移**：控制任务的已知官方/流程目标来自解构时冻结草稿目录（`_prepare_source_in_session`:462-602），与正式 RuleSet 修订无任何链接；`rule_component_ids` 参数默认空、无 plan 兜底。目录发布必须用绑定修订的官方编号/组件 ID 重解析并传入门禁，否则可能发布引用不存在条款的控制。
- **节点 ID 空间漂移**：绑定里的 `workflow_stage_id` 来自冻结源 `workflow-stage-<hash>`（`protocol_control_execution.py:794-824`），而正式节点按 `{rule_set_id}:{revision}:` 命名空间化（`protocol_publication_service.py:576-592`）。发布时须按 (review_stage, visit_instance) 确定性翻译并对不上者拒绝。

步骤：
1. 新建 `app/services/protocol_control_catalog_publication_service.py`（模板：`ProtocolPublicationService` 的事务形态——幂等键+谱系检查+`expected_rule_set_revision` 乐观锁，`protocol_publication_service.py:203-477/290-300`）：读控制任务 gate 检查点中已持久的候选包（publication_plan+batch_dispositions）→ 确定性晋升每个候选为 `ProtocolReviewControl`（`protocol_control_id`=目录上下文+originating_candidate 稳定哈希；display_ordinal 按来源序；跨源关系端点 CONTROL_CANDIDATE→PROTOCOL_CONTROL 改写；节点 ID 翻译）→ 构造非空目录 → 以绑定修订目标集调用 `validate_protocol_control_publication`。
2. 持久化：复用 `AppendRepository`+`encode_contract`（`repositories.py:1503` save_rule_set 同型）：新 `ProtocolControlCatalogRecord`（catalog_id 主键；scope: protocol_version_id/study_phase/rule_set_id/rule_set_revision；payload+sha）。同事务追加控制来源 `ControlMinimumEvidence` 期望模板（due 闭包以目录自身 review_node_bindings 校验，不改已冻结的 `WorkflowStage.due_requirement_ids`，也不动 `ProtocolAuthorityRecord`）。
3. 消费：`get_current_control_catalog(session, rule_set_id, revision)`（None 安全）；`_all_requirements`/期望投影增加控制支；实时投影增加控制区（按节点角色定适用性、按义务 modality 区分阻断/提醒、经 cross_source_relations 显式呈现重复/补充/冲突、无官方编号回退）；`assemble_review_context` 冻结完整目录；报告从冻结读取；目录缺失或有候选未晋升时范围说明可见"控制未材料化"，不得报告全方案已审（T3.2/§17.3）。
4. 不做：控制 DNF 谓词化求值、ClausePack v1 扩展、按疾病/药名补丁、新队列。

统一验收时的失败用例（现在不建测试）：修订被抢先（拒绝）、关系目标不在绑定修订（拒绝）、节点翻译失配（拒绝）、有候选但目录空/未晋升无记录（拒绝或范围说明）、SUBSTANTIVE_CONFLICT 阻断（现有）、DUPLICATE_STATEMENT 共享评估身份下游去重不并显示、控制证据双到期/缺到期、新目录修订不改写历史冻结审核、recommended/best_effort 不渲染为阻断。

### 四、决策点与有界问题（需 Codex 裁定）

- **Q1（最高影响）晋升政策**：合同无逐候选接受/拒绝字段，现语义是包级全过或全败。安全暂定：仅自动晋升通过完整非空目录门禁的候选，未晋升者带原因进范围说明；若要求人工逐条确认则需新增处置合同。请裁定。
- **Q2 控制资料期望接入深度**：共享 `EvidenceRequirement`/模板链（T3.1"共同消费"，但引入双到期闭包来源）vs 先只做控制侧投影（blast radius 小，但违背 §17.2 唯一缺口语义的风险）。我建议前者+目录侧闭包，需你确认。
- **Q3 页审提示是否需要包含控制陈述**：期望模板路径已可覆盖资料读取；若模型还需看到控制原文，才需要 pack v2 文本条款。

**未验证范围**：仅静态代码/设计审阅，未跑测试、未调用模型、未验数据库实际行；`_validate_control` 内部各保真检查的语义正确性未逐条复核（属临床验收范畴）。工作目录内未发现阻塞性缺失输入。
