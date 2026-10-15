# Codex Execution Plan: enrollment-mtplx-serial-adapter-20260916

Objective: 为入排产品双MTPLX建立显式串行生命周期适配，先审计现有调用与资源所有权，提出最小完整修改。禁止临床规则或来源数据变化。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审查 app/llm/page_review_harness.py、app/services/page_review_execution.py、page_review_runtime.py 及相关本地资源准入，输出串行加载、释放、预检、取消、跨作业互斥的具体接入建议与文件定位；不修改应用文件，不启动模型，不调用产品推理，不新建测试；报告到 runs/execution/enrollment-mtplx-serial-adapter-20260916/serial-review.md。 | `runs/execution/enrollment-mtplx-serial-adapter-20260916/worker_01.md` |

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
