# Codex Execution Plan: phase5-large-parent-segmented-glm-live-probe-20260901

Objective: 在不修改冻结临床源资料、旧探针、旧任务和已暂停 D001 的前提下，使用生产 ProtocolDeconstructorRunner 与 GLM-5.3-Flash high 对大型父规则执行四段真实语义解构，记录耗时、模型身份、原始响应、确定性合并和发布门结果，并与既有整段 GLM 探针进行独立质量及性能对照；不得触发未授权 fallback。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读预检冻结源包、生产运行器、GLM 传输适配器和凭据加载路径；形成最小真实探针方案，证明规划器输出四段且不泄露凭据、不改写旧产物。 | `runs/execution/phase5-large-parent-segmented-glm-live-probe-20260901/worker_01.md` |
| `worker_02` | 运行新的真实分段 GLM-5.3-Flash high 探针：复用生产运行器和传输，最多两路并发，保存每次调用的模型身份、耗时、原始响应、合并候选与发布门结果到新的独立产物目录；失败时保留证据并停止，不自动切换模型。 | `runs/execution/phase5-large-parent-segmented-glm-live-probe-20260901/worker_02.md` |
| `worker_03` | 独立只读比较新分段结果与既有整段 GLM 结果：核对源覆盖、义务项、逻辑/时间锚点、例外、证据要求、发布门、错误和耗时；检查是否存在 D001/SAR 特异硬编码，仅给出证据化结论，不自行宣布临床最终验收。 | `runs/execution/phase5-large-parent-segmented-glm-live-probe-20260901/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
