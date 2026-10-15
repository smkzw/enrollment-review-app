# Codex Execution Plan: phase5-selective-vision-single-page-e2e-20260901

Objective: 在全新隔离数据目录中，以一页内容中立的风险资料验证冻结证据修订到选择性视觉任务、智谱Coding Plan GLM-5.3-Flash真实调用、不可变观察落盘和用户查询投影的完整闭环；不得读取或修改D001/SAR旧结果，不得新增项目特异规则，不得以流程返回成功替代来源、观察正文与OCR不变性核对。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审阅现有独立VLM真实连通测试、证据修订种子、视觉后处理执行器和观察仓储，提出最小单页隔离端到端验证方案、必要输入和失败判据；不得修改文件。 | `runs/execution/phase5-selective-vision-single-page-e2e-20260901/worker_01.md` |
| `worker_02` | 作为唯一代码写者，在不新增依赖、不修改既有临床来源的前提下，优先复用测试夹具建立可显式启用的单页真实视觉端到端测试；只有发现通用根因时才做最小生产修复，并运行聚焦检查。 | `runs/execution/phase5-selective-vision-single-page-e2e-20260901/worker_02.md` |
| `worker_03` | 只读独立攻击端到端验收设计与写者产物，重点核对是否真的走zhipu-token-plan等价Coding Plan端点、是否形成非空且来源匹配的观察、OCR原文/哈希是否不变、失败是否关闭、状态投影是否反映落盘结果；不得修改文件。 | `runs/execution/phase5-selective-vision-single-page-e2e-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
