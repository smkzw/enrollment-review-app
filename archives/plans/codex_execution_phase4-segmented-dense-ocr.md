# Codex Execution Plan: phase4-segmented-dense-ocr

Objective: 为密集表格页面实现可复现、可审计的分段OCR，避免模型输出循环和截断，同时保持共享oMLX门控、不可变工件和页面顺序合同。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 分析现有OCR执行、工件身份和共享门控，提出最小兼容设计。 | `runs/execution/phase4-segmented-dense-ocr/worker_01.md` |
| `worker_02` | 实现通用密集页判定、稳定空白分割、逐段OCR与原始响应保留。 | `runs/execution/phase4-segmented-dense-ocr/worker_02.md` |
| `worker_03` | 补齐确定性测试与真实密集实验室报告探针，不修改任何临床原始资料。 | `runs/execution/phase4-segmented-dense-ocr/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- 普通页面保持单段路径与原行为；密集页只由通用图像特征触发。
- 分割线优先落在低墨迹水平带，分段从上到下稳定、无倒序、无超界、无空段。
- 每段独立进入共享 OCR 门控，任一段截断或失败时整页不得生成成功 OCRPage。
- 原始请求、各段原始响应、分段坐标与合并文本均进入内容寻址、可回放工件；缓存指纹包含算法版本和段身份。
- 单元/集成测试覆盖普通页、密集页、顺序、响应保留、截断、重试和租约计数。
- 使用只读 D001 密集实验室页做真实探针，结果不得再出现异常循环，且不能以“流程成功”代替内容合理性检查。
