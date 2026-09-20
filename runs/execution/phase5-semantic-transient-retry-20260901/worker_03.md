# 执行输出：phase5-semantic-transient-retry-20260901 - worker_03

## 边界与上下文检查

- 工作目录为 runner 绑定的 worktree `.../enrollment-review-app/.worktrees/phase5-clinical-facts-profile`，分支 `codex/phase5-clinical-facts-profile`。未读取或修改任何生产路径；未安装任何包；未创建或修改任何文件（本角色为只读审阅 + 回归执行）。
- 已读初始上下文:`context/phase5-semantic-transient-retry-20260901_execution_context.md`、`plans/codex_execution_phase5-semantic-transient-retry-20260901.md`，以及已落盘的同批报告 `runs/execution/phase5-semantic-transient-retry-20260901/worker_01.md`、`worker_02.md`（作为证据，非指令）。
- 为独立审阅额外读取的源文件（只读）:`app/agents/deepseek_protocol_transport.py`（全文）、`app/agents/protocol_deconstructor.py`（SAR 恢复路径 3556-4531 行）、`app/protocols/parent_rule_semantic_segmentation.py`（闭包校验与合并 330-397 行）、`app/protocols/deconstruction_gate.py`（`evaluate` 及 11 项检查）、`app/services/protocol_deconstruction_executor.py`（路由回退 640-830 行、输入包装配 945-1010 行）、`tests/v2/protocols/test_protocol_transport_transient_retry.py`、`tests/v2/protocols/test_segment_capability_checkpoint_recovery.py`（部分）。
- 结论先行：**worker_01 的暂态重试与既有 SAR 恢复路径组合后，三项保证均成立**——完整性门禁未被削弱、无项目规则硬编码（且有强制回归测试守护）、不重复结构提取。聚焦回归 255 项全部通过。

## 已执行工作

**1. 独立审阅 SAR 恢复路径与暂态重试的交互（代码级证据）**

- **重试预算收敛**：传输层 `_send_completion`（`deepseek_protocol_transport.py:356-390`）每次重试重放逐字节相同的 kwargs（模型、消息、response_format 均不变），最多 3 次尝试、退避 2.0s×attempt；超时类（`APITimeoutError`/`httpx.TimeoutException`/`TimeoutError`）首遇即抛，保留 `TRANSPORT_TIMEOUT` 分类；4xx 不匹配任何重试元组，直接穿透。耗尽的暂态错误以默认 `SEMANTIC_CALL_FAILED` 上抛（`protocol_deconstructor.py:89`），分段恢复层 3625 行对其**立即**转 `ProtocolParentSegmentError`，不追加恢复——SAR 级新鲜传输重试仍然只属于超时（最多 1 次），且重试前强制校验传输身份（分段支持声明、wire 合同一致、`retry_cache_key == cache_key`，任一漂移即 `TRANSPORT_IDENTITY_CHANGED` fail-closed，3631-3665 行）。
- **完整性门禁未削弱**：① 分段闭包校验 `validate_segment_source_closure`（只允许分段冻结 span 集合、必须引用正文来源）对缓存候选、新鲜候选、合并结果三处均执行（3613、3680 行；`parent_rule_semantic_segmentation.py:384`）；② runner 主循环对**每一次**解析出的草稿（含恢复产出）都跑完整 `ProtocolDeconstructionGate.evaluate`（identity/phase_scope/parent_catalog/tree_integrity/boolean_logic/numeric_semantics/temporal_semantics/workflow_coverage/evidence_coverage/source_coverage/interpretation_authority/diff_integrity 共 11 项，4347 行起），最终结果携带 `final_gate_result`，executor 持久化 gate 版本与 `publishable`；③ 回归守卫 `regressing_rule_codes` 会在修订使此前通过的规则退化时先还原再重新过门禁（4355-4376 行）——恢复不会静默降级已通过状态；④ fail-closed 由既有测试断言：`test_double_timeout_fails_closed_without_publishing_segment`、`test_partial_segment_failure_does_not_publish_merged_parent`。
- **无项目规则硬编码**：对 5 个 SAR 相关模块 grep 药品名/项目名/生物标志物（阿利沙坦/信立坦/康哲/ECOG/RECIST 等）零命中；重试常量为通用数值（次数、退避秒数），后端选择走枚举，阈值全部来自 config。更强证据：既有强制回归测试 `test_segmentation_recovery_modules_contain_no_project_specific_hardcoding` 会全文扫描传输模块（**含 worker_01 新增代码**）、executor、分段模块及 deconstructor 分段辅助函数块，断言不含 `D001/EX-06/IN-01/ALT/AST/ULN/ECOG/RECIST/Nivolumab/阿帕替尼` 等项目特定字面量——本次运行通过。
- **不重复结构提取**：结构提取发生在 freeze 步骤并持久化 checkpoint；generate 步骤从 checkpoint 反序列化冻结 `source_input`（`protocol_deconstruction_executor.py:1000-1010`），所有恢复路径复用同一冻结输入。分段计划与提示词每次运行只构建一次；SAR 重试复用同一 `prompt`、同一 `segment`、同一 `cache_key` 并做相等校验。`_hydrate_semantic_candidate` 明确"由目录持有结构装配，不要求模型复写结构"。checkpoint 复用（失败段单独重试、成功段不重跑）由 `test_successful_segment_is_reused_from_checkpoint`、`test_only_failed_segment_is_retried_while_successful_segments_reuse_checkpoint` 断言。
- **上限核算（推断，非缺陷）**：单逻辑请求最坏 HTTP 调用 = 分段内 3（传输暂态）或 1+1（超时新鲜传输）；分段整体失败时整父回退恰好一次（`test_segment_failure_falls_back_once_to_whole_parent`），自带 ≤3 次暂态尝试；graded 路由模式每候选一次、带审计台账，重试只是把单次尝试的 HTTP 调用乘以 ≤3，不改变路由尝试次数。全部有限、可审计。

**2. 独立运行聚焦回归（自选 10 个文件，比 worker_02 的 6 个更广）**

覆盖：新故障注入测试、传输 slice3、SAR checkpoint 恢复、父规则语义分段、分段修复、传输配置、完整性门禁、语义模型路由、MTPLX 路由回归、路由预检。**255 passed**，详见下节。

## 工件与证据

- 本角色零文件产出（按分工只审阅与回归）。审阅对象：worker_01 的 `app/agents/deepseek_protocol_transport.py` 改动（未提交）、worker_02 的 `tests/v2/protocols/test_protocol_transport_transient_retry.py`（14 个故障注入测试）。
- 新测试文件抽查为实质断言：恰好 3 次调用、三次 kwargs 逐项相等、退避 `[2.0, 4.0]`、4xx/超时恰好 1 次调用零等待、耗尽后会话历史完整保留且 `continue_session` 可恢复、中文恢复日志（“方案解构模型服务出现暂态传输错误（第1/3次尝试）……重试"）、`sk-secret` 密钥不出现在 `str()`/`repr()`/caplog。

## 命令与观察结果

- `.venv/bin/python -m pytest tests/v2/protocols/{test_protocol_transport_transient_retry,test_deepseek_protocol_transport_slice3,test_segment_capability_checkpoint_recovery,test_parent_rule_semantic_segmentation,test_parent_rule_hierarchical_segmentation_remediation,test_deconstruction_transport_config,test_deconstruction_gate_slice3}.py tests/v2/agents/{test_protocol_semantic_model_routing,test_mtplx_semantic_route_regressions,test_protocol_semantic_route_preflight}.py -q` → **255 passed, 5 warnings（仅 SwigPy DeprecationWarning，无关）**，2.66s。
- `grep` 项目特定字面量（阿利沙坦/信立坦/康哲/ECOG/RECIST/ULN 等）于 5 个 SAR 相关源文件 → 零命中（观察）；强制守护以 `test_segmentation_recovery_modules_contain_no_project_specific_hardcoding` 通过为准。
- 环境验证：openai 2.37.0 / httpx 0.28.1 / pytest 9.0.2（与 worker_01/02 记录一致）。

## 阻碍或缺失的环境

无。环境齐备，所有审阅与检查在声明边界内完成。

## 重跑请求或下一步

- 无需重跑。供 Codex 验收的两条非阻塞观察：① `_try_collect_parent_segments` 对分段路径的**全部**异常做整父回退（3816-3822 行），最坏情况下分段暂态耗尽仍会多付出一次整父调用（≤3 次 HTTP）——有界、有测试断言、符合"恰好一次回退”设计，如需更严格的分段级错误上抛需另行决策；② `app/llm/client.py` 异步 `_retry` 及兄弟同步传输（evidence_normalizer、phase_applicability）仍无 5xx 重试，与本次改动不冲突，是否对齐由 Codex 决定。
- 最终验收（Codex）：确认 255 项聚焦回归结果与本审阅结论，随同 worker_01/02 产物一并纳入提交。
