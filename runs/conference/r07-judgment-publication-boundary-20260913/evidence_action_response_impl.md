继续只读复核办理链实现：先对命令、仓储、合同与前端办理入口做完整核对。# Conference Output: r07-judgment-publication-boundary-20260913 - evidence_single_object

## Output

只读复核办理链实现。未改代码、未跑测试、未读库。不是临床签收。`derive_review_action_directive` 未接发布器，不记成全链已通。

### Findings

1. **低：幂等命中返回的修订号按请求推算，不读库存。** `review_action_command.py:65-73` 在回执命中后返回 `expected_revision + 1`，即使此后已有另一次办理、`previous.revision` 更大。同键同体不会重写，但客户端可能拿到过期修订。  
   **最小改法：** 命中时返回 `previous.revision`（转换已在列表中）。不要为此改状态机。

其余验收点在源码上已按上次边界落地，未见必须立刻改的高/中缺陷。

### 无问题范围（相对本轮验收）

- **人工办结要理由和回应原件。** 合同：`CLOSED_MANUAL` 必须非空 `locator_ids`，说明去空白（`review.py:336-341`）。命令：办结无定位或重开却带资料版本则拒（`review_action_command.py:98-101`）。前端：无说明或未选定位不能提交（`ReviewActionResponseDialog.tsx:64,116`）。
- **只记办理，不改临床结论。** 命令只追加 `ActionRequest` 转换并换 gate/指纹（`104-133`）；不写 `FinalAssessment`。文案写明结论不变（对话框 88 行；报告 122 行）。
- **同受试者同节点、可新快照。** 写路径钉当前 `episode.revision` 与活动 snapshot/complete（`84-97`）。`validate_action_response` 只要求权威的 project/subject/episode 与 Action 相同，然后 `validate_frozen_source` + `validate_locators`（`review_reference_validation.py:53-69`）。`validate_frozen_source` 不核当前活动指针（`fact_authority.py:88-95`）。历史 `_stored_actions` 对每条转换走同一冻结核验并另装定位（`review_history_service.py:418-424`）；原件面板仍用原 `context.authority`（`498-504`）。报告用 `ReviewResponseEvidenceDTO` 单独打开「办理回应原件」（`review_history.py:384-391`；`FrozenReviewReport.tsx:128-130`）。
- **追加一条、身份与触发不可变。** `replace`：v2 除 `state/transitions/revision/fingerprint/gate_result_id` 外必须相等；旧转换为前缀；恰好 +1 条（`repositories.py:2362-2376`）。触发定位只按冻结 `context.authority` 验（`588-604`）。v2 办理不再拿当前 `episode.rule_set_*` 去卡。
- **幂等与冲突。** 同 scope/键/哈希先读回执；异哈希 `IdempotencyConflict`（`review_action_command.py:64-68`；`idempotency.py:116-124`）。修订不符在写之前拒绝（`74-75`）。API 单事务 `session.begin()`（`review_actions.py:37-39`）。仅 `close_manual`/`reopen`（`13-17,76-81`）。无新表/队列。路由已挂（`app.py:369-370`）。
- **条款模板一致性在上下文合同，不在办理命令。** 同身份要求必须与 ClausePack 字段一致；模板可多于条款（`review_context_v2.py:171-181`）。`derive_review_action_directive` 只描述已有缺口、不改判定（`review_action_directives.py:22-37`），**无其它引用**，发布器未接。

### 待最终测试（非本轮实现缺陷）

未跑并发同键、修订冲突、补传后历史 GET、前端选页/保存。`validate_frozen_source` 仍要求该 complete 为 `ready` 且 `is_activatable`（`fact_authority.py:194-198`）；完整修订合同本身禁止改成不可激活（`evidence_locator.py:1064-1065`），但未实测旧 complete 在多次激活后是否仍可读。办理按钮仅 `run.status === "completed"`（`FrozenReviewReport.tsx:104-107`）：未完成报告不能登记办结，属产品范围，不是仓储错误。

不建议：伪造 AgentCall、把类别候选当证明、为出报告放行全部未知。本切片只处理回应与历史保存。
