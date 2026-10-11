收到 1006V1 跨界来源证明补丁独审任务。按边界：只读、不落盘、不委派（Trellis 任务与计划文件不适用）。先定位补丁新增符号。

定位完成。读取见证实现与集成点（4 个并行）。

# Conference Output: rv1006-source-scope-resume-review-20261011 - evidence_single_object

## Output

**审阅范围与限制（先声明）**：只读当前 worktree；未取 git diff（Bash 不可用），补丁按符号/正文直读重建；未读真实方案/病例/DB/env/私有运行；未运行产品任务；未委派。本轮 12 次只读调用已用满（4 定位＋8 读取）。Trellis 任务/计划文件与本指派边界不符，未创建。以下 **[代码事实]/[推断]/[建议]/[不确定]** 分层；**不称临床批准、发布或 Q3 完成**。

---

### 1. 来源/表号/列/期别/文档/hash/完整性：是否有未保护的误归属

**[代码事实] 定位保护比上轮建议更紧，且全部"重derive相等"而非"接受声明"**：
- 表号：`_table_reference` 只从属主单元 `heading_path[-1]` 的"表N"题注正则取物理标识（`control_scope_sources.py:30-34`），见证中的 `table_reference` 必须等于重derive值且出现在前文原文中（`:154-156`）。
- 对象/列：`table_sequence_source_packet`（`:37-102`）要求属主为 `table_row`、`.r<n>` 与 `row_index` 一致；被引句在同一文档根内**恰命中一个单元格**且其 refs ⊆ 属主 `member_source_refs`（`:52-59`，重复措辞→None，测试 `split=True`）；表头必须是 `table_header`、同行表上方（`source_order`/`row_index`，`:62-70`）；合并表头必须**完全落在动作列内**且不重叠（`:78-83`，跨对象合并→拒绝），且列覆盖必须恰好闭合（`covered == action_columns`，`:95`）。
- 期别/文档：`_same_source_scope`（`:18-27`）校验 `study_phase`、`phase_scopes`（另一期别→拒）与 span 文档标记；前文段另受 `source_order < 属主`、`heading_path` 前缀、`source_unit_sha256`/`source_span_ids`/`source_excerpt` 逐项重derive（`:139-157`）。
- 对象完整性：见证 `object_citations` 必须**逐字节等于** packet 重derive结果（`:158-160`），且每个对象文本必须出现在先后依据原文内（`:161-162`——这是"不能借用另一种治疗的关系"的机械防线；测试 `missing_object/other_object` 覆盖）。
- 25 例合成测试含 16 个破坏变体（`test_slice58c_control_deconstructor.py:3931-3974`：错表号、常用词、跨文档、跨期别、后置、坏hash、坏span、缺/错对象、缺/后置/异文档/异期别表头、改表头、重叠合并、重复表头）＋6 个关系变体（`:3977-3994`）。**[代码事实]** 方向明确交给模型：`:3997-4006` 断言位置清单照旧给出且 packet **不含** `eligibility_sequence`（"Location never proves the order"）。

**[不确定/P2] 两个未完全覆盖面**：
1. **文档隔离在无 `"::"` 标记时退化**：`_same_source_scope` 只在 span 含 `::` 时比较文档（`:25` `not any(documents)` 直接放行）；且前文段校验不含 `source_ref` 根前缀相等。若冻结 span 不带文档标记，跨文档误归属只能靠期别/标题/顺序兜底。**[建议]** 要求文档标记或前文与属主的 `source_ref` 根相等（廉价、fail-closed）。
2. **例外/背景保留不对称**：跨章先例要求另一端保留本条时间与例外（`source_interpretation.py:2317-2322` `CONTEXT_RELATION_DIMENSION_MISSING`），而新表格顺序路径只检查**对象覆盖**（`:161-162`），不检查 `exception_words`/背景。**[建议]** 在见证路径（interpretation 或 review 校验）补一条同类要求：语句携带例外/背景时，不得仅凭研究治疗对象的存在走 `not_current_control`。
**[必须]** 不要把定位保护表述为临床语义证明：时序方向、对象归属语义、例外适用性仍是核对模型的判断；代码只证"位置与字节"。此点与所有者要求一致，但销售/文档层面须明示。

---

### 2. 重用身份、旧字段、保存/读回、采用消费者相容性；跳过 fresh 核对或伪造 not_current_control 的漏洞

**[代码事实] 相容性与防线基本成立**：
- 见证纳入重用身份：`_source_statement_reuse_identity` 现含 `eligibility_sequence_context` 的稳定 JSON（`protocol_control_deconstructor.py:7347-7348`）→ 见证任何变化即使该陈述旧复用失效；`:7537/8631/8959/8987/9825` 的逐条比较随之生效。
- 旧可选字段：`eligibility_sequence_context` 为 `exclude_if None` 可选字段（`source_interpretation.py:277-279`），旧解释可解析；同单元旧路径原样保留（`:3347-3356`）；**未声明 after 却携带见证**被拒（`:3357-3360`）。
- 假造 `not_current_control` 的堵口：跨单元情形要求（a）见证在校验器内重derive通过（`:2350-2354`）、（b）核对条目回显**同一** `SourceSequenceContext`（`:2355-2357` `POST_ELIGIBILITY_CONTEXT_UNCONFIRMED`）、（c）`non_control_basis_excerpt == eligibility_sequence_quote`（`:2362-2365`）、（d）不得残留候选（`:2366-2368`）、（e）不得有未决面（`:2369-2371`）。无见证时仍走"同单元、动作之前"老规则（`:2358-2361`）→ **跨单元无法凭旧路径过关**。
- 保存/读回：`test_table_sequence_witness_is_read_proposed_saved_and_consumed`（`:3895-3928`）真实走 Runner→保存→`_validate_saved_source_review`：缺 review 抛错、前文原文加一句即拒；核对回显与解释见证逐字段相等（`:3920`）。执行层 validator 版本串已纳入 `TABLE_SEQUENCE_SOURCE_VERSION`（`protocol_control_execution.py:2095-2100`），组件身份变化会使旧 checkpoint 需刷新（比较点 `:2934/3522`）。
- 采用消费者：`is_post_eligibility_calculation`（`source_interpretation.py:1184-1196`）只认已校验的 `not_current_control` + 功能 ⊆ {action, calculation_input} + 无未决；消费于 `protocol_control_execution.py:5088` 与 `protocol_control_catalog_publication.py:115`。**[推断]** 未见"跳过 fresh 核对"的代码路径：新决策只能由一条通过上述五关的核对条目产生。

**[必须核实的 P1 候选]** `SourceTargetReviewItem.non_control_sequence_context` 的**字段必填性**我未读到（预算用尽，仅见使用处 `:2355` 与测试显式传入 `:3891`）。若声明为必填（无默认），则**所有历史保存的 review 载荷**（不限 not_current_control 条目）在 `model_validate` 时会失败 → 相容续跑变成硬失败。**[建议]** 确认其为 `None` 默认可选；若已必填，改为可选并用 `:2355` 的相等检查强制 fresh 回显。这是本补丁我最需要的单项确认。

**[不确定]** 核对提示词改动仅见测试断言（`"不能根据上一位作者的 after 标签关闭要求"`，`:3910`；解释提示 `"位置清单不是先后含义证明"`，`:3906`），未读正文，无法核实提示是否明确要求"独立判断方向"而非"回显"。

---

### 3. 独立读取策略：总两次上限的后果与新版 Job 继续方案

**[代码事实]**：`_INDEPENDENT_DEEP_READ_POLICY`（`protocol_control_execution.py:257-264`：`deep_` + {STU, SCR} + `max_failed_steps: 2`）随 opt-in 冻结进 job payload（`:1048-1054`）；`_continue_independent_after_failure`（`app/workflow/runner.py:244-271`）按 **本 job 全量** 统计 `step.state=="failed_final" and step_id 前缀 and step.error_code in codes`，`prior_failed + 1 < 2` 才继续；继续时 `_commit_step_failure(settle_job=False)` 并回到取步循环（`:475-486`）；停止即 settle，依赖级联终败（`jobstore.py:1551-1588`），其余 queued 步不再运行。

**[推断/必须] 拟议的"新版 Job 继续"按现状不成立（P1）**：新 job 若把两个已失败单元作为**保留失败**重新落地，保留分支会以**原错误码**抛 `StepFailure`（`protocol_control_execution.py:4477-4484`，`error_code=proof["error_code"]` ∈ 白名单）→ 它们在新 job 内再次计入 `prior_failed`：第二个保留失败即 `1+1<2` 假 → 直接 settle，**41 个未读单元仍然读不到**。即"新 job 计数器自然清零"的直觉被"携带的失败步再次计费"抵消。
**[建议] 最小完成（三选一，均不动 1006V1 边界）**：
1. **首选（计数器语义修正）**：`prior_failed` 只统计**本次运行实际发起的失败**，或显式排除带 `preserved_unresolved_from` 诊断的步骤（保留分支已在诊断里写了该标记，`execution.py:4480-4483`；runner 已持有 store，可读取该步最近 checkpoint 的有界字段）。改动仅限 `runner.py:265-270` 一处，白名单/前缀/`max_failed_steps` 全部复用 → **单份 policy 真相**。
2. 或让新 job 的计划**不重新进入**保留失败步的计数面（例如把其步骤定义为计划外终态，仅作为 gate 依赖），但这会动计划/依赖表达，风险高于 1。
3. 最次：为新 job 抬高上限——**不建议**（等于第二份真相或版本化放宽，且无系统性失败防线）。
**反证（支持保留总两次上限）**：同一 job 内上限是**系统性失败**的唯一刹车——若来源/表格整体变更导致多单元语义失败，无上限继续会把剩余 41 单元额度烧在一个基础材料可疑的批次上；且本策略的注释（`execution.py:1064`："a second stops. Publication remains blocked."）表明这是有意设计。**因此建议：job 内保留 2 次上限；跨 job 继续走显式授权的新版 Job（含上述计数器修正），而非放宽上限。** 每步预算：既有 `source_repair_limit` 单调上限（`execution.py:4581-4586`）保证复用步不刷新；未读步为首次执行，本就不存在"刷新"。终态/发布依赖不变（保留失败仍终败、gate 仍级联失败、无共同发布）。
**[建议] 反证测试**：新 job 中两个保留失败步以 0 调用落地且**不消耗**新计数器；第 1 个新语义失败仍允许独立步继续、第 2 个停止；身份/结构/传输错误码不在白名单→立即停止；预算上限不因新 job 提高。

---

### 4. 结论（必须 / 建议 / 证据不足）

**必须**：① 确认 `non_control_sequence_context` 为可选默认字段（否则旧 review 载荷读回硬失败，P1）；② 若采用新版 Job 继续方案，先修 `runner.py:265-270` 的计数口径，否则方案无效（P1）；③ 对外表述不得把位置保护称为时序/临床语义证明（方向由模型核对，测试 `:3997-4006` 自证）。
**建议**：④ 文档隔离兜底（无 `::` 标记时要求 `source_ref` 根相等或强制标记）；⑤ 例外/背景保留检查对齐跨章先例（`:2317-2322` 对 `:161-162`）；⑥ 补"新 job 不重复计费/上限不放宽"的回归测试。
**证据不足**：`_schedule_cells_from_units` 的单元格/合并列语义未读（packet 列覆盖逻辑依赖它）；核对提示词正文未读；`non_control_sequence_context` 字段声明未读；validator 版本失效链仅经 grep 取证（`execution.py:2095-2100`、`:2934/3522`）。**决定性不确定**：真实冻结 span 是否恒带 `"::"` 文档标记（决定 P2-④ 是理论还是实际缺口）。

**独立性折减**：同族模型（仅适配器/上下文不同）；本报告为源码合同级审查，不构成医学批准，也不替代完整 1006V1 流程。**给 Codex 的有界问题**：Q1 字段必填性？Q2 是否授权 `runner.py:265-270` 的计数修正（首选方案）？Q3 真实 span 文档标记形态？
