# Phase 5.8d 通用两阶段候选控制点生产链检查点

日期：2026-08-31  
状态：候选控制点生产链已验收；正式控制点目录未物化；`claims_complete=false`

## 已完成

- 用户原始上传的 DOCX/PDF 只进行一次结构化读取，后续任务消费冻结结构快照。
- 全方案结构清单恰好进行一次高召回发现，发现结果严格分为 `candidate/context_only/non_control/uncertain`。
- 仅候选和不确定项进入独立模型深度解构；其余来源仍进入确定性全文闭包。
- 持久化执行器、动态深度步骤、检查点恢复、进程恢复、幂等 API 和失败分类已接通。
- “需要核对”是不可盲重试的终态；公开 API 不暴露内部批处理和上下文参数。
- 返回结果准确标记为水合候选控制点包，正式目录状态为未物化。
- 新链路不调用旧版 reviewer，不通过 D001/SAR、药物、疾病、量表或特定条款词表探测候选。

## 验证证据

- 聚焦测试：102 passed。
- 全仓测试：3295 passed，3 skipped，18 subtests passed。
- `py_compile`、`git diff --check` 通过。
- 执行审计：`phase5-protocol-control-discovery-production-integration-20260831` 返回 `ok=true`。

## 尚未完成

- 未运行真实独立模型的端到端生产 harness。
- 未以 D001 与 MG-K10-SAR 进行同一 harness 的只读异构回放。
- 未实现候选控制点到正式 `ProtocolReviewControl` 的受控转换与发布。
- 未进入受试者审核、Patient Profile、前端或浏览器视觉验收。

## 下一安全动作

1. 用词汇中立的极小合成协议运行一次真实生产 harness，记录发现分布、深度范围、解析修复、延迟与失败分类。
2. 冒烟通过后，以完全相同的提示、合同和门禁分别运行 D001 与 MG-K10-SAR 只读异构回放。
3. 不因任一真实项目添加共享项目特异规则；先比较覆盖闭包和错误模式，再设计候选到正式控制点转换。
