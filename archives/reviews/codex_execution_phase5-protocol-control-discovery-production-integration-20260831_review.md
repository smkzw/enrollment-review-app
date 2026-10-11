# Codex Execution Review: phase5-protocol-control-discovery-production-integration-20260831

## Verdict

`ACCEPT_CANDIDATE_CHAIN_ONLY`

本轮仅验收“结构快照 -> 全方案高召回发现 -> 确定性闭包 -> 候选/不确定项深度解构 -> 候选控制点包”的生产链路。正式 `ProtocolReviewControl` 目录尚未物化，不得据此声称方案解构或发布已经完成。

## Worker Outputs

- `worker_01`：完成生产接线边界审计，确认源文件只结构化读取一次、旧版 reviewer 不得进入新链路、发现与深度解构必须拆分。
- `worker_02`：实现严格发现传输与解析；全量结构清单恰好发现一次，输出仅允许 `candidate/context_only/non_control/uncertain` 及必要上下文。
- `worker_03`：实现持久化执行器、任务服务和最小 API。首稿因把“需要核对”作为外层可重试失败、返回空正式目录且暴露工程参数而被拒收；随后沿同一会话修正为不可盲重试的终态，并准确返回 `hydrated_candidate_control_package` / `formal_catalog_status=not_materialized`。
- `worker_04`：补充通用化和生产回归，覆盖快照冻结、动态深度步骤、进程恢复、幂等复用、参数拒绝及禁止项目词表探测依赖。

## Manager Assessment

本路线没有 execution manager 节点，Codex 直接承担处置。首次 `worker_03` 结果被拒收，原因是状态语义、正式发布边界和公开接口均不满足产品合同；修正使用原会话继续，没有换模型或以新会话掩盖失败。修正版可以作为候选链生产基础，但不能进入正式控制点发布。

## Codex Independent Verification

- 聚焦测试：`102 passed, 5 warnings`。
- 全仓测试：`3295 passed, 3 skipped, 141 warnings, 18 subtests passed`，耗时 `641.58s`。
- 三项跳过均为既有外部锚点不可用：MG-K10-SAR 保存规则、MG-K10-SAR/06003 证据锚点、本地真实 oMLX 探针工件。
- `py_compile` 与 `git diff --check` 通过。
- 正式 `audit-execution` 返回 `ok=true`；四名 worker 均按声明的 `pi/openai-codex/gpt-5.6-luna:max` 完成，无 fallback。
- 尚未运行真实独立模型、D001/SAR 全协议异构回放、候选到正式控制点转换、前端与浏览器验收，`claims_complete=false`。

## Boundary

本轮边界止于候选控制点生产链。正式控制点目录、真实模型语义质量、真实项目覆盖率、受试者判定和用户界面均不在本轮验收范围；任何空目录、候选包或通过的模拟传输测试都不能替代这些后续验收。

## Hermes

四个受控 worker 均使用 guard 声明的 `pi/openai-codex/gpt-5.6-luna:max` 路由，runner 日志完整且无 fallback。正式 `hermes_workflow_guard.py audit-execution` 返回 `ok=true`；一次 prompt preflight 失败发生在模型启动前，未计作 worker 完成或路由失败。

## Cleanup Decision

验收后可归档本轮执行过程文件；保留执行上下文、复核、指标、runner 日志和 Trellis 检查点。下一步仅做小型、词汇中立的真实模型冒烟测试，成功后再以 D001 与 MG-K10-SAR 作为只读异构语料运行同一通用 harness。
