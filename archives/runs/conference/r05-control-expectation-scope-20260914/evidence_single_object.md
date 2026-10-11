证据收集完成。我已完整读取控制合同四层 DNF、发布合同、模板投影、期望 v2 投影服务、缺口信号、判断检索来源、条款包与发布事务写边界，并核对了设计书 §17.3 与恢复计划 T3/T5 的当前状态。以下为本角色的完整会议输出。

---

# Conference Output: r05-control-expectation-scope-20260914 - evidence_single_object

## Output

**结论（证据 → 推断 → 建议分列）**：「按匹配阶段的显式 DECIDE 节点各投影一次」可从已发布显式绑定推导（不是从 fact_type 猜测），但**不被既有期望合同支持，不能直接实施**；应先在 `ControlMinimumEvidence` 上增加显式证据—节点绑定（可选字段＋发布门禁强制模式），再走第三条“控制来源要求”通道进入模板/期望。理由与最小接线方案如下。

### 发现（按影响排序）

**F1 多节点投影与现有合同结构性冲突，且读侧已有三种不一致行为。**
模板合同是“一要求一节点”标量：`requirement_due_twice`/`requirement_without_due_stage` 硬失败（app/projections/evidence_expectation_templates.py:81-98），`workflow_stage_id` 单值（app/domain/contracts/evidence.py:156）。同一资料绑同一阶段 ≥2 个 DECIDE 节点时：受试者期望投影服务对“同阶段另一节点模板”**硬报错**、刻意拒绝猜测到期（app/services/evidence_expectation_projection_service.py:77-82），而缺口推导与审核投影对同一条件**静默跳过**（app/services/fact_expectation_gaps.py:236-239；app/services/eligibility_review_projection.py:423-429）。Episode 本身按节点建（app/domain/contracts/review.py:87-115）。任何多节点接线必须先统一这三处语义，否则要么整次投影失败、要么缺口静默消失。备选：每节点独立 requirement 身份（保持 due-once 不变量，推荐）vs 放宽 due-once（破坏模板身份算法，不推荐）。

**F2 证据—节点绑定应先入 schema。**
现门禁只保证：evidence.due_stage ∈ 绑定节点阶段，且每个 DECIDE 阶段有对应到期证据（app/protocols/protocol_control_gate.py:3465-3477）；**不保证** evidence.due_stage 处存在 DECIDE 绑定（如该阶段仅 EARLY_ATTENTION、DECIDE 在后段，门禁合法）。此时读侧推导得到零个到期节点 → `requirement_without_due_stage` 失败或无模板。且 EARLY_ATTENTION/LATER_NODE_REVIEW 角色在模板通道无承载字段，硬投影为 due-once 即丢角色语义。建议在 `ControlMinimumEvidence/Draft` 增可选节点绑定，门禁校验其 ⊆ 所属控制同阶段 DECIDE 绑定，沿用 `affected_workflow_stage_id` 的“旧记录可解码为 None、新发布门禁必填”先例（app/domain/contracts/protocol_controls.py:1440-1443）。

**F3 控制来源要求需第三 origin 通道，且必须同事务写入。**
`EvidenceRequirement` 校验器与存储 CHECK 均为 rule_component XOR procedure_catalog_item（app/domain/contracts/rules.py:291-297；app/storage/models.py:396-410）；模板落库 FK 要求 requirement 行实存且在节点 `due_requirement_ids` 内（app/storage/repositories.py:2882-2895、2956-2962）。流程必做项是现成先例：草稿侧提案 + `save_rule_set(procedure_requirements=...)`（repositories.py:1503-1514）+ 传入投影器（protocol_publication_service.py:933-944）。关键顺序约束：不得改已发布 WorkflowStage.due_requirement_ids——draft/published 节点内容全等校验（app/protocols/control_catalog_materialization.py:133-141）与 ClausePack v2 的 rule_set_sha256 复核（app/projections/clause_pack.py:142-146）会破坏。故推荐**平行 due 闭包**：`project_evidence_expectation_templates` 增 `control_requirements` + 节点映射入参，requirement 行与模板在 `publish()` 同一事务落库（控制发布保存在 protocol_publication_service.py:464-472，模板在 :1035）。requirement_id 直接用系统身份 `evidence_key`（"pce-"，protocol_controls.py:2621-2629），目录内唯一性已有合同（protocol_controls.py:1622-1624）。

**F4 模板语义字段的有损默认。**
`ControlMinimumEvidence` 缺 `requires_contemporaneous_objective_source`/`allows_screening_record_transcription`/`source_validity_window`（protocol_controls.py:1399-1413），而义务原子携带 temporal_scope/time_constraint（:184-215）。静默取默认（False/True/None）会放宽强度。最小方案：义务带时间范围而证据侧无表示时**fail-closed 拒绝发布**，仅 CALENDAR_LOOKBACK→TimeQuantity 可定显式映射。义务强度同理：门禁已强制证据描述保留“建议/尽力”措辞（protocol_control_gate.py:945-993），但期望状态机无非阻断通道（evidence_expectations_v2.py:218-269；fact_expectation_gaps.py:287-302），RECOMMENDED 证据会与 mandatory 同样产生 absent 阻断缺口——需要“已请求资料文档”非阻断呈现层（可报告缺失，不要求用户反复确认，不阻断）。

**F5 条件适用性：无共享求值器前不得变无条件阻断。**
适用性/触发/例外 DNF 需要素材求值，frozen 审核对非空控制显式拒绝（frozen_review_calculation.py:37-38），T3 明示此限制须保留直至链条完成（plans/...IMPLEMENTATION_PLAN...md:77）。故第一阶段控制来源期望只能以“资料已请求、适用性未确认”可见层进入，确认后才转正式到期判定；不得从 fact_type/节点名/疾病词推适用（§17.1/§17.3 一致）。判断检索侧：procedure 来源被显式拒绝（judgment_search_source.py:287-295），控制来源需自己的显式分支与原文解析（其原文在 protocol source spans，不在规则行内），不能套 rule-component 路径。

**F6 去重。** `DUPLICATE_STATEMENT`+`shared_assessment_identity`（protocol_controls.py:1471-1475）是评估共享身份而非行合并；两条控制要求同一资料应保持两条 requirement 行（各自来源闭包），在审核上下文/报告层用关系去重呈现，合并行丢来源闭包。

### 待 Codex 裁决的合同问题
1. 同阶段兄弟节点模板：按 episode 节点收窄投影范围＋“属同阶段另一节点”呈现（推荐），还是新增状态/缺口类型，或暂不支持多节点证据？
2. 无同阶段 DECIDE 匹配的最低证据：要求显式“仅资料请求”处置，还是强制 Agent 补绑定？
3. `shared_assessment_identity` 是否映射单一共享 requirement 行（我建议否，见 F6）？
4. 义务时间范围→`source_validity_window` 映射规则是否仅限 CALENDAR_LOOKBACK、其余拒绝？

### 下一实施边界（最小通用、顺序）
① F2 的 schema+门禁 → ② F3 第三 origin（合同、存储 CHECK、save_rule_set/save_expectation_templates 扩展，同事务） → ③ 投影器 control_requirements 入参＋三处姐妹节点语义统一 → ④ F4/F5 非阻断呈现层＋适用性指针＋judgment_search 控制分支 → ⑤ 保持 frozen_review_calculation 拒绝与 v1 历史/ClausePack v2 冻结不变（模板 v1 哈希兼容 evidence.py:166-172、215-222；ClausePack v1 序列化 clause_pack.py:49-55），直至 T3 剩余链条完成。未执行任何模型、测试、数据库或应用修改；本报告为只读审阅，不构成临床或最终验收。
