# Conference Output: r05-proposition-consumer-20260915 - evidence_single_object

## Output

同会话跟进 pass（只读源码；未编辑/导入/运行）。范围：F3 收窄修复的回归与缺失相邻版本消费方。**结论：未发现不安全接受或确定性路径回归；版本升级链完整。F4 撤回（我此前引用错误）。** ≤45 行，证据/建议分列。

### 证据（已核实）
1. 版本升级完整：常量 v4（`app/domain/contracts/binding_qualification.py:27`）；job 载荷 contract Literal 扩至 v4（`:312`）；summary contract 同（`BindingQualificationSummary.prompt_version`）；授权 `qualification_prompt_version` Literal 扩至 v4（`app/domain/contracts/qualified_binding_selection.py:50`）。v2/v3 保留可读，旧记录哈希稳定。
2. 标记门精确：`app/services/binding_qualification_support.py:583-588` 仅当 `determination_mode ∈ {semantic, investigator_judgment}` 且 `fact_attribute ∈ {value, assertion_basis}` 且 `spec.operand_attribute ∈ {None, 该属性}` 才置 `bound_assertion_for_proposition`；`fact.assertion_basis.locator_id != pair.locator_id` → `assertion_source_not_bound`（结构无效）。谓词分支（`:555-572`）未动，无谓词侧泄漏；确定性规格仍走旧分支（`:589-596`）。
3. 严格拒绝保留：标记不在拒绝集（`app/services/qualified_binding_selection.py:92-97`）；冻结体/来源政策核对仍覆盖标记配对（support`:536-554`）；双路好态、source_policy、admissibility、denial_scope、temporal_role 要求不变；`remaining_unverified` 不新增该标记（support`:793-798` 仅旧三种 shape）；`operand_shape` 为开放 `str`（contract`:223`）故旧记录无 contract 破坏，且 summary 与重算比对（support`:1057-1059`）阻断伪造 shape。
4. pending 交互：基础两项仅在双路好态豁免；`source_unverifiable`、`pending:source_validity_requires_policy_evaluation`（semantic+source_validity 规格）、`pending:professional_judgment_applicability_unverified`（investigator 判断谓词）仍拒绝。
5. v4 提示边界正确：`app/llm/binding_qualification.py:174-181` 文字陈述≠数值操作数；direct/usable 须无猜测/拼接；明确“不表示原文支持或否定命题……原文含义由另一步核实”。validator 守卫未变（`:197-215`：批次一致、source_policy 前置、record_time 禁冒充）。提示材料经 pair.condition 携带规格，determination_mode 可达。
6. F4 撤回：`app/domain/contracts/proposition_method_evaluation.py:10` 实为 `proposition-evaluation-manifest/v1`（父类 Literal 在 `judgment_method_evaluation.py:30`，我此前误引父类值）。

### 建议（非阻塞）
- A1（用户可见后果）：v3 已完成资格任务在 `support:971-974` prompt 门处不可再消费 → 进行中的 v3 工作流无法发布，须在 v4 下重跑 verification（retry 不复活已完成子任务）。fail-closed 与提示文本/消息哈希变化一致，但需在发布说明/界面提示。
- A2（浪费读取，方向安全）：proposition 输入加载器不查 `operand_attribute` 兼容性（`proposition_evidence_input.py:37-39`），标记门查（support`:585`）→ 少数语义配对被读模型后落入 `unresolved_proposition_pairs`（`operand_shape_declared_operand_attribute_mismatch`）。不可用但不危险。
- A3（范围确认，接上轮 Q3 未答）：本修复实际解锁的是 `semantic` 规格；`investigator_judgment` 谓词带 `requires_professional_judgment` 者仍因 `pending:professional_judgment_applicability_unverified` 被排除（control 族 `written_content_verified` 恒 False，`qualified_binding_selection.py:370`）。请确认此为预期范围。
- A4（数据前置，F2 已确认 pending）：审批 gate 评测记录须记载 `qualification_prompt_version=v4`（`require_evaluated_binding_method` 以 `verified["prompt_version"]` 比对），未重签前发布端持续 fail-closed。

无缺失的相邻版本消费方：judgment_content、proposition-evidence/v1、selection v3/consumer v7、evaluator v9、publication v4 均不受本变更影响。
