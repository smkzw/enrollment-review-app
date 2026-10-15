Trellis SessionStart context loaded.

Proceeding as a bounded read-only reviewer. First, mapping the delta against 674dfffa.

Bash is denied in non-interactive mode; I'll work read-only via file tools and note the delta-tooling limitation.

No standalone diff artifact available; I'll review the named current definitions directly. Locating them.

Core definitions read. Now locating the helper contracts and the tests that exercise them.

# 工程审查报告（只读 · 非验收/非临床批准）

**证据边界**：本会话 Bash 被权限拒绝，无法计算相对 `674dfffa` 的精确 git diff；结论基于当前工作树中指定定义与合成测试的 15 次聚焦读取，未运行任何测试（集中测试窗口未完成，不构成验收）。模型独立性受限：本 reviewer 可能与产品路线同属 DeepSeek 家族，但未执行任何产品临床工作。

---

## 问题一：完整有源 procedure 单元 + typed temporal + 相关 additional action，能否整单元 NON-EXECUTABLE 保留？

**结论：可以（在类型化前置条件下），未发现阻断级缺陷。** "上一轮 single-temporal procedure 拒绝"保持：单陈述 procedure 临时项在整单元 gate（`restricted_source.py:466-473`，`additional_requirement` 需 `uncertain∩` 或 `len>1 且 temporal∩`）与逐条路径（`gate.py:4930-4933` 要求 `decision_functions==["action"]`）双双拒绝。

判定链（`app/services/protocol_control_restricted_source.py`）：
- 类型门 `_temporal_restriction_indexes:133-183`：error_classes 精确集合、`json_path/retry_class/statement_ids` 严格类型、`affected_dependents==ids`、`source_refs` 必须等于 temporal 单元 span 并集，缺一即 `None`。
- 不吞无关要求：`158-165` 要求 `indexes<=additional` 且 `additional-indexes` 全部落在 temporal 同单元、纯 action、非 definition/calculation_input、未 unresolved；跨单元无关 additional → 整批拒绝（测试 `test_..._cannot_absorb_unrelated_additional_source:645-653`、`test_mixed_procedure_extension...:574-586`）。
- 不丢兄弟：`456-478` 单元门后，`511-552` 对受控单元 **全部** statements 生成 restricted records；`501-510` 共享候选/残留候选跨 span 一律拒绝。
- 不制造来源歧义：纯 temporal 情形 `limitation_kind=consumer_unavailable`（`534-535`）且维度用单元级措辞；来源不覆盖即拒绝（`_unit_statements_cover_source:54-76` + 测试 590 的 `unread_prefix`）。
- 不授予采用：disposition 被重建为 `RESTRICTED_SOURCE` 且丢弃 linked 程序目录 id（`557-560`，测试断言 `linked_procedure_catalog_item_id is None`）；定义登记校验只回查实际回答、**不改变来源 disposition**（`_validate_restricted_definition_registration:570-593`）；持久化证明 `adopted: False`（`execution.py:2905-2917`），投影 `fact_refs=()`、非解读类 `action_owner=None`（`eligibility_review_projection.py:1437-1457`）。
- 危险反例：若去掉 `158-165` 的 `indexes<=additional` 或 `501-506` 的共享候选检查，无关 additional 会被吸收、跨单元候选会被静默删除——当前两处都会整体拒绝。正例：`test_typed_temporal_procedure_retains_all_same_unit_actions_without_adoption:590-642` 全 defect 变体均返回 None。

**保守限制 L1（非阻断，可选冻结外建议）**：`_whole_unit_restriction:513-545` 以"单元内是否存在 unresolved"（`temporal_only`）统一决定 `limitation_kind`。混合单元（typed temporal + unresolved 兄弟）时，temporal 陈述自身的能力因被折叠为 `interpretation_unresolved`（测试 `889-923` 断言），投影随之按"方案待澄清"把该条目路由给申办方医学（`eligibility_review_projection.py:1431-1456`）。最小修正（会改已断言行为，建议冻结后处理）：按 statement 保留各自 limitation 因，或在任何情形下都把 temporal 自身维度文本加入 `unresolved_dimensions` 并让 owner 随陈述自身因。

## 问题二：缺失本地前缀/对象上下文的 saved-source 恢复路径

**结论：路径窄、宿主不填充来源，未见阻断缺陷；有三项保守/局限。**

- 入口与硬门：`execution.py:2773-2795`（要求同源+已保存 review 仍有效+gap 存在+`indexes` 非 None）；`procedure_correspondence_source_gaps:79-96`、`procedure_correspondence_scope_indexes:99-122`；消费端 `deconstructor.py:7242-7281` 只调用有界 reader 提案，`apply_source_context_completion`（`source_interpretation.py:594-618`）强制逐字前缀、`scope[1]<=quote[0]`、整单元连续覆盖，partial/wrong-unit/unresolved 全部拒绝（测试 `656-684`）。正例：完整前缀提案被接受且原文不动；危险反例：若接受 partial prefix（如仅"所测项目"），单元会看似被覆盖而对象含义丢失——当前 `611-616` 拒绝。
- 不完整/传输/畸形不成为 restriction：`restricted_source.py:616-620, 818-825` 不接受 `SOURCE_CONTEXT_*` 类；失败结果是"需要核对"（`deconstructor.py:7289-7308`）。
- R1（保守）：`99-122` 仅接受"单元唯一陈述 + 引文起点>0 + 引文达单元尾"的前缀缺失形状；中段缺失或尾部文本 → None → 回退整读，成本型，不产生采用。
- R2（保守）：`execution.py:2788-2789` 当 `source_seed_proof is not None` 时整个 resume 返回 None（而非走已验证 seed 或继续受限恢复），属更严格拒绝。
- R3（提示词级）："不得吞入独立要求"仅存在于 prompt（`deconstructor.py:7270-7273`），硬门无法语义区分"范围标签"与"被吞动作"；残余风险受限于该陈述 `unresolved` 不被清除、变更陈述仍需来源/目标核对（docstring `600-604`）。另发现可选不一致点（未验证、低置信）：`apply_source_scope_question_recheck:510-521` 丢弃 `apply_source_scope_correction` 的 phase-label 归一结果后直接赋 `revised`，是否与 `571-581` 归一不一致取决于 `validate_source_interpretation` 覆盖度。

**未读依赖（降低置信）**：`check_protocol_control_batch_candidates`/`_saved_deep_run_result`/`_validate_deep_batch_output` 内部；`RESTRICTED_SOURCE` 与 `restricted_statements` 在评估执行侧的其余消费（仅读了 `eligibility_review_projection.py:1428-1459`）；deconstructor 全量 runner 重审路径；相对 `674dfffa` 的 diff 未能计算（Bash 拒绝）。本报告仅为工程审查，无测试运行、无验收与质量金标声明。
