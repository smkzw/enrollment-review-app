# Codex Execution Plan: phase5-protocol-control-discovery-production-integration-20260831

Objective: 将已验收的通用两阶段方案控制点发现与深析合同接入可持久化生产执行链：原始DOCX/PDF结构化一次，全清单由独立模型高召回发现，只有候选/不确定单元进入深析，确定性代码负责身份、闭包、上下文、重试与发布门禁；不得加入任何项目、疾病、药物、量表、时间点或阈值硬编码。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计现有 discovery/deep transport、runner、executor、jobstore、API 调用链，提出并实现最小通用接入边界；不得手工解释协议内容。 | `runs/execution/phase5-protocol-control-discovery-production-integration-20260831/worker_01.md` |
| `worker_02` | 实现 discovery 专用严格结构化 transport/runner 与有限同会话修复，使模型输出仅能提交四类处置、理由和必要上下文，身份与闭包由系统掌控。 | `runs/execution/phase5-protocol-control-discovery-production-integration-20260831/worker_02.md` |
| `worker_03` | 实现可恢复的 protocol-control executor/job/API 编排，复用一次性 DOCX/PDF 结构快照，串接 discovery→deterministic closure→deep→hydrate→gate，禁止回落到 legacy reviewer。 | `runs/execution/phase5-protocol-control-discovery-production-integration-20260831/worker_03.md` |
| `worker_04` | 增加合成与异质只读回归测试，证明无 D001/SAR 特例、无词表过滤、无全文反复深析；用 fake transport 验证失败/修复/恢复/门禁路径，并明确真实模型运行仍属后续验收。 | `runs/execution/phase5-protocol-control-discovery-production-integration-20260831/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
