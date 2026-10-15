All verification complete. The ownership marking is symmetric across child types. I've now covered every file in the assigned scope plus the supporting chain (receipts, lane reconstruction, ownership, progress, API, layer composition, identity projection). Compiling the final report.

# Conference Output: r05-proposition-consumer-20260915 - evidence_single_object

## Output

独立只读源码审阅（grok 402 终态不采信，本次为全新独立 pass；仅源码，未运行测试/模型/数据库，未修改任何文件）。结论：**主链未发现 source-proven blocker**；版本授权、严格纳入、见证方向、空任务与工作流接线与声明意图一致。以下按证据/推断/建议分层，≤70 行。

### 已核实的不变量（证据）
1. 版本链授权 v4/selection v3/consumer v7/evaluator v9 (`component-review/v9`)/publication v4 全部钉死并交叉校验：`app/domain/contracts/qualified_binding_selection.py:21-23`、`app/services/qualified_review_command.py:114-116`、`app/services/frozen_review_publication.py:95-98`；proposition consumer 独立版本 `qualified-proposition-evidence/v1`（`app/services/qualified_proposition_evidence.py:6`）。proposition manifest 通过 `source_qualification_method == binding_method` 全量等值传递性钉住 evaluator/publication 版本（`qualified_proposition_evidence.py:16`）。
2. 旧序列化输入保留原字段：`<v4` 授权与 `<v3` 选择的 wrap serializer 剔除 proposition 字段（contract `:69-74`,`:165-171`），validator 拒绝回填并从哈希材料剔除（`:190-206`）；旧 gate `output_hash` 复验字节稳定（`app/services/qualified_binding_selection.py:139`）。
3. 严格纳入：仅 `pair_direct_selection_rejection_reasons` 为空 + identity 一致 + 双路 agreed 的关系入选（`app/services/qualified_proposition_evidence.py:58-73`），默认旗标（不豁免专业/时间不确定性）。
4. 见证方向纪律（`app/projections/control_calculation_experiment.py`）：无观察→UNKNOWN 非_false（`:42-43`）；缺关系记录→UNKNOWN（`:69-72`）；带时间→UNKNOWN（`:73-74`）；single+semantic→UNKNOWN（`:49-50`）；反向见证（ANY-全FALSE / ALL-全TRUE）→UNKNOWN（`:64-66`）；同 fact 关系冲突→UNKNOWN（`:75-77`）；争议组→UNKNOWN（`:200-204`）；确定性原子只用代码计算（`:190-195`），关系记录不能注入未选事实（`:147-155`）。
5. 空任务不调模型（`app/services/judgment_content_job.py:111-119`）；发布端无 pairs 不要求关系评测（`app/services/prepared_review_publication.py:50-56`）。
6. 工作流：仅 v3 排程 `control_proposition_evidence`（`app/services/prepared_review_workflow.py:241-242`,`:299-304`）；v1/v2 保留旧 expected 集（`:236-240`）；`workflow_job_id` 经候选任务继承（`app/services/review_runtime_ownership.py:42-45`）；OWNED_TYPES/进度/视图/API 均接线（`prepared_review_progress.py:16,44`、`app/api/v2/qualified_review.py:29`）。
7. 回执/路由核验完整：`_verify_call_sequence` 重放 429/length 策略并核 route_identity（`app/services/judgment_content_receipts.py:39-78`）；双路须异模型（`app/services/proposition_evidence_comparison.py:16-17`）；来源绑定逐字段（`qualified_proposition_evidence.py:31-41`）。

### 发现（按影响排序）
- **F1（中高，语义设计问题，非逻辑错误）**：ANY 模式下跨事实矛盾被吸收——不同 fact 一 entails 一 contradicts 时 observations=[TRUE,FALSE]→直接 TRUE 且无冲突标记（`control_calculation_experiment.py:54-59`）。同 fact 冲突已捕获（`:75-77`）、争议组已捕获（`:200-204`），但跨事实矛盾在 ANY-TRUE/ALL-FALSE 决定性结果中静默。建议：给决定性结果附加非阻塞 reason（如 `proposition_witness_conflict`）或要求见证集无矛盾；属 Codex 政策决定。
- **F2（运行前置条件，非源码缺陷）**：正式路径要求 `ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID` 指向的 gate 其 `evaluation_manifest_sha256s` 含 `pair_local_proposition_relation` manifest 并钉住当前链（`qualified_review_command.py:138-144`、`frozen_review_publication.py:80-92`）；否则一律报“采用确认未覆盖本次原文含义核实”。源码无法确认持久化 gate 数据，需 Codex 核对审批数据已重签。
- **F3（声明的保守性限制，确认存在，不应称完整）**：严格复用算术资格拒绝原因致语义材料不可用——operand_shape_*、`pending:source_validity_requires_policy_evaluation` 等与 pair-local 语义无关的检查同样拒绝（`qualified_proposition_evidence.py:60-62` 调 `qualified_binding_selection.py:54-125` 默认旗标）；且 control 族 `written_content_verified` 恒 False（`qualified_binding_selection.py:370`）。未入选对以 unresolved 可见，无静默 false，方向安全。
- **F4（低）**：`PropositionEvaluationManifest` 沿用 `judgment-evaluation-manifest/v1` 版本串，仅靠 `evaluation_kind` 区分（`app/domain/contracts/proposition_method_evaluation.py:10-11`）；按 version 单键消费方会误路由。union 校验当前正确；建议下次修订用独立版本串。
- **F5（低，效率）**：发布路径对 proposition evidence 最多 3 次全量重建（`prepared_review_publication.py:52`、`qualified_review_command.py:137`、`qualified_proposition_evidence.py:29`），只读且正确，代价是 artifact 读放大。
- **F6（方向性已验证）**：命题按原文原方向（`app/llm/proposition_evidence.py:56`），trigger/exception 方向在层组合处理（`app/domain/control_layer_evaluation.py:95-110`）；identity 含完整 atom dump，spec 变更即换身份（`app/projections/control_atom_binding_input.py:28-37`），陈旧关系无法改接。

### 给 Codex 的有界问题
- Q1（对应 F1）：ANY-TRUE 见证是否要求“见证集无 contradicts 记录”或仅附加标记 reason？两者均为一行级修改，等待裁决。
- Q2（对应 F2）：请确认审批 gate 数据已含 proposition manifest；若未重签，当前代码在发布端 fail-closed，属预期。
- Q3（对应 F3）：control 族 investigator_judgment 身份未来是否允许书面判断豁免，还是永久严格（影响可用语义材料比例）？

**不确定性声明**：`calculate_control_operands` 内部与 `JobStore` 检查点机emons为既有共享机emons，仅按调用契约核对其边界；持久化 gate/审批数据、`ENROLLMENT_REVIEW_METHOD_APPROVAL_GATE_ID` 实值不在源码可证范围。未运行任何测试（用户延期至整build）。恢复点：如需跟进，建议针对 F1 的 `control_calculation_experiment.py:51-66` 聚焦复审。
