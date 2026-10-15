# Codex Execution Plan: phase5-selective-vlm-page-triage-20260831

Objective: 为独立GLM-5.3-Flash视觉模型建立通用、按页面风险选择的最小业务接入：原生文本优先，只有扫描、复杂表格、结构异常或OCR低置信页进入视觉核验；保留来源定位、失败关闭、费用时延可控和业务路由隔离，不恢复D001。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审阅Phase 4/5设计、当前证据处理链与独立VLM合同，提出最小页面风险判定合同、输入输出和禁止边界，不修改文件。 | `runs/execution/phase5-selective-vlm-page-triage-20260831/worker_01.md` |
| `worker_02` | 作为唯一生产代码写入者，在证据处理/共享服务边界实现通用的选择性视觉核验规划与调用适配；不得修改测试文件、OCR执行器语义或D001工件。 | `runs/execution/phase5-selective-vlm-page-triage-20260831/worker_02.md` |
| `worker_03` | 仅修改新的独立测试文件，为页面风险选择、原生文本跳过、扫描/表格/结构异常/低置信进入、失败关闭、来源保真和无项目特异硬编码建立确定性测试；不得修改生产文件。 | `runs/execution/phase5-selective-vlm-page-triage-20260831/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
