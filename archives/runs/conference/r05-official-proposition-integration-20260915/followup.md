# 会议输出：r05-official-proposition-integration-20260915 - evidence_single_object (后续)

## 输出

后续只读复审已完成：在当前工作树中重新打开了全部六个修复面及其相邻消费者（相关文件为未提交的新增/修改，工作树即现状，未用旧快照）。结论：**D1/D3/D4/D5/D6/D7 全部通过；发现 1 项新的流程级缺陷（N1：消费算法语义变更未升版本号）与 1 项数据库依赖的未验证项（N3）；D2 提出了带源头证据的最小接线规格。** 未运行测试、未导入应用、未触碰数据库/浏览器/模型。

### 一、逐项裁定

**D1（单次范围未核实的未定原因污染）— 通过**
`app/domain/proposition_observations.py:14-18`：该分支现在无条件首先包含 `observation_scope_completeness_unverified`，随后才追加观察自身的 codes（含正向标记 `prospective_statement_verified`，作为补充信息而非主因）；`proposition_observations.py:37-39` universal 反方向确定结论现在保留全部观察的备注性 codes（含"声明不代表履行"标注）。发布层合并（`frozen_review_publication.py:152-155`）与前端映射均兼容。真值逻辑未变，仅原因呈现修正。

**D3（命题证据采用强制）— 通过**
- 双族强制：`app/services/qualified_binding_selection.py:412-421` 从冻结输入推导 `requires_proposition`（predicate 族=任一 `semantic_proposition`；control 族=任一 semantic/investigator_judgment evaluation），缺失采用即抛出 `InvalidJobDefinitionError`（"没有可核对原文时也须保留检查记录"）。
- 零对任务全链可完成：入队仅含 summary 步骤（`app/services/judgment_content_job.py:111-119`），回执校验对空批次安全（`proposition_evidence_receipts.py` 空比较循环不迭代），工作流 ready 门要求该子任务到达终态（`prepared_review_workflow.py:287-302`）。
- 工作流发布：`app/services/prepared_review_publication.py:51-59` 在 `identity_coverage` 非空时挂接命题任务（其取值集合与 `requires_proposition` 同源于冻结输入，`proposition_evidence_input.py:30-39` 对照 `qualified_binding_selection.py:412-419`，判定一致）。
- 直接提交同样受控：`submit_qualified_review` → `publish_frozen_review:99-101` → `build_receipt_verified_qualified_binding_selections`，缺失即在同一强制点失败（呈现为 `qualified_review_command.py:65-68` 的通用 `ScopeViolationError`，仅文案层面不精确，非缺陷）。
- 工作流过期防继承：`prepared_review_workflow.py:42-56` 在发布时钉扎五类任务的 contract+prompt_version，不匹配即拒绝发布旧工作流。

**D4（批级校验脆弱性）— 通过**
读取器移除了两条策略级批杀校验（`app/llm/proposition_evidence.py:148-149` 注释明示移交消费侧）；身份/命题哈希、引文⊆locator 摘录、未来期间、研究者判断依据等严格校验原样保留（`:126-147,150-153`），合同层 schema 校验器未动（`proposition_evidence.py` 合同 `:83-104`）。消费侧按对隔离：`app/services/qualified_proposition_evidence.py:77-85` 对 universal-under-wrong-policy 与 policy-None 时的范围输出追加 `proposition_scope_policy_mismatch`，该对进入 `unresolved` 并保留原始双路回答，同批无关配对不受影响。新 code 已接入缺口映射（`app/domain/gates/assessment.py:218`）与前端说明（`frontend/src/domain/reviewConditionNotes.ts:11`）。

**D5（选择层状态簿记）— 通过**
`qualified_binding_selection.py:512-518`：policy 为 None/mode=unresolved/带 selection 任一情形均追加 `observation_selection_unverified`，语义条件不再可能以无效政策进入 usable；control 侧同样补齐（`:594-595`）。算术路径专属原因对语义条件有意丢弃（修复说明所述），关系路径自有的日期资格与配对完整性检查仍在（`:508-525`）。残余记录：`:507` 的覆盖仍会丢弃 `_select_with_ordering` 的 `observation_scope_reasons` 输出，但配对级 `scope_candidates_complete`（`:508-511`）覆盖同一枚举完整性关注点，且设计明示"逐事实考虑仅限所供事实"——可接受，仅记录。

**D6（未核实证据分离）— 通过**
- API：新增 `ReviewHistoryUnverifiedEvidenceDTO`（locator 级+逐对原因，`app/api/v2/review_history.py:135-138`），条件 DTO 将 `not_selected` 收窄为仅排序审计排除（`:441-446`）、`unverified_evidence` 独立成列并按 locator 聚合原因（`:426-428,447-450`）。同一事实可同时出现在采用事实与待核实原文中——合同校验仅禁止 `fact_ids` 与排序未选重叠（`app/domain/contracts/review.py:214-217`），不禁止与命题缺口重叠，符合"同一事实既有已核实段落又有待核实段落"的场景。
- 历史：读侧校验未变（`review_history_service.py:396-404`：命题身份匹配 + locator ∈ 事实定位集合），无待核实在定位 (locator) 被静默采纳。
- 字节稳定：存储模型可选字段空时仍从序列化中弹出（`review.py:226-235`），旧记录不回填；DTO 默认空列表，前端 `exactKeys`（`reviewHistoryHttp.ts:497`）对新旧载荷一致。
- 前端：解码器强制非空原因（`reviewHistoryHttp.ts:518-524`）；UI 逐缺口原生说明+"查看待核实原件"按钮（`FrozenReviewReport.tsx:119-124`），查看器按 `doubtLocatorId` 精确过滤定位（`:231-243`）；导出包含待核实条目（`frozenReviewExport.ts:40,58`）。（审阅中两次 rg `-r` 误用替换标志造成的 `condition.n` 显示伪影已排除，源码字段名正确。）

**D7（前端映射缺项）— 通过**
`reviewConditionNotes.ts:6-11` 补齐 `selected_observation_missing`、`no_usable_qualified_pair`、`event_date_not_qualified_for_selected_value`、`multiple_usable_pairs_without_selection_policy`、`identity_absent_from_qualification` 并新增 `proposition_scope_policy_mismatch`。

### 二、新发现缺陷

**N1（不通过——消费算法语义变更未升版本）**
`qualified-binding-selection-consumer/v12`（`app/domain/contracts/qualified_binding_selection.py:23`）与 `qualified-proposition-evidence/v5`（`app/services/qualified_proposition_evidence.py:8`）在本次行为变更（强制命题采用、策略隔离、策略缺失阻断 usable）后**未升级**。任务级钉扎（`prepared_review_workflow.py:54-56`）只覆盖任务 contract/prompt——本次均未变，故旧工作流/旧授权在语义已变的消费代码下仍能全链通过校验。变更方向严格保守（确定→未定、缺失→抛出），且所有材料 `accepted=false`，实际风险取决于 N3；但这违反项目自身的"不同版本不可冒充同一运行"纪律——方法评测/批准一旦对 v12/v5 签发，其语义即被静默改写。
最小修正：在签发任何评测清单/方法批准前，将两个常量升级（需同步扩展合同 Literal 枚举），现时零迁移成本。

**N2（备注，不构成不通过）**
`app/domain/gates/assessment.py:206-238` 的 REASON_GAPS 仍缺 `no_usable_qualified_pair`、`identity_absent_from_qualification`、`no_candidate_pairs_in_completed_job`、`written_content_unverified`、`multiple_usable_pairs_without_selection_policy`、`event_date_not_qualified_for_selected_value` 等映射；这些码经 `:338-344` 兜底为 RECORD_INCOMPLETE、判定 INDETERMINATE（`_decision_for_unknown`），无正确性漏洞，仅缺口分类偏粗，可选择性补齐。

**N3（未验证）**
数据库中是否已存在绑定 consumer v12 / 命题消费 v5 的 binding-evaluation 清单或 method-approval 门。无数据库访问权限，无法核实。若无，N1 降为卫生问题；若有，升级后须重新签发。

### 三、D2 半衰期——源头证据与最小接线规格

**决定性证据**：旧载体 `ReviewContextSnapshot.half_life_days`（`app/domain/contracts/context.py:18`，内容寻址入 `context_sha256`）仍被遗留评估路径消费（`app/domain/gates/assessment.py:558,645`），但现行正式上下文 `ReviewContextSnapshotV2` **无此字段**，且 `calculate_frozen_review` 构造 `EvaluationContext` 时从不传入（`app/services/frozen_review_calculation.py:216-222`）→ 恒空。同时解构器可合法产出 `half_life_multiplier`（`protocol_deconstructor.py:529`；门禁按子项原文数字核验倍数，`deconstruction_gate.py:2558-2567`；与日历窗并存须显式 `combined_window_selection`，`rules.py:125-133`），故半衰期约束可进入已发布规则集而在正式审核中永久 UNKNOWN。

**最小、源头受限的接线（建议）**：半衰期天数属于方案药物属性，应随规则版本冻结而非自由漂浮的上下文字段——解构时若 TimeConstraint 使用 `half_life_multiplier`，要求方案原文同时给出该药物半衰期（或倍数句内含数值），以 TimeQuantity+逐字来源引用提取，按谓词 `subject.attribute` 键存入 RuleModelRevision/ClausePack 的 `half_life_days`；发布门禁对"有倍数无来源数值"失败关闭（与现有 `不填造` 门禁模式一致）。`calculate_frozen_review` 随冻结包传入一行即可（`frozen_review_calculation.py:216-222`），`expression.py:374-378` 与 `predicate_proposition_calculation.py:73` 不需改动。方案只写倍数、任何地方无数值时，按不可核实拒绝该约束，而不是留给永久 UNKNOWN——这与"阈值、药物属性来自当前方案原文"（设计 §5）一致，且历史哈希稳定（数值随规则修订冻结，不在审核时重推导）。

### 四、其他指定检查项

- **官方事实选择与关系计算**：`_select_facts_for_identity`/`_select_with_ordering` 未变；语义分支覆盖逻辑如修复说明成立（见 D5）；`predicate_proposition_calculation.py`（106 行）未变。
- **父工作流/零对完成**：入队、ready 门、发布三层均已核实（见 D3）；`publish_prepared_review` 要求工作流 completed+任务版本现势+依赖全完成（`prepared_review_publication.py:18-42`），幂等键 `prepared-review-publication:{workflow_id}` 为新命名空间，无历史继承问题。
- **提示词版本 (Prompt 版本)**：`proposition-evidence/v6` 与提示词文本未变（读取器改动仅在验证侧），job/summary 合同保持 v3——与"验证侧放宽、消费侧隔离"的修复结构自洽。

### 五、决策点（Codex）

1. N1 版本升级时机：建议在任何方法批准签发前完成（一行常量+Literal 扩展）；是否随本切片执行请裁决。
2. D2 接线载体：随规则修订冻结（本报告建议）抑或恢复上下文字段——前者更源头受限，后者改动更小但需要独立的来源引用核验。若采纳前者，需解构合同新增字段并过发布门禁，属相邻实现。
3. N2 的映射补齐为可选项，建议与 N1 同批。

**总体**：六项修复均按描述落地且未引入正确性回归；阻塞项仅 N1（流程纪律，须在批准签发前处理）与 N3（依赖数据库事实）。以上为源码审阅结论，不构成临床、生产或最终验收。
