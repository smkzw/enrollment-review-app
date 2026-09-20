# Codex Execution Plan: phase5-slice61aq-native-pdf-structure-entry-20260829

Objective: 在不调用临床模型的前提下，为V2方案解构建立项目无关的原生文字PDF结构化入口：用户直接上传PDF后进入与DOCX相同的冻结StructureBlock/ProtocolExtractionSnapshot/来源定位链；扫描或文本层不足时失效关闭为需要核对；原PDF直接用于页面文本与定位，不伪装成DOCX结构，也不引入项目特异规则。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计现有DOCX结构、PDF原生坐标、方案工作流与来源定位合同，给出最小兼容设计、风险和验收反例，不修改代码。 | `runs/execution/phase5-slice61aq-native-pdf-structure-entry-20260829/worker_01.md` |
| `worker_02` | 实现项目无关的原生文字PDF到统一StructureBlock和ProtocolExtractionSnapshot的确定性解析器与格式分派，保存页码/文本范围所需稳定身份，扫描或文本层不足时返回结构化异常，不调用OCR或模型。 | `runs/execution/phase5-slice61aq-native-pdf-structure-entry-20260829/worker_02.md` |
| `worker_03` | 把PDF结构入口接入方案解构执行器、重放harness和上传格式边界，补充合成/真实只读回归、格式分派、原PDF渲染复用、扫描失效关闭和路径/哈希/确定性测试。 | `runs/execution/phase5-slice61aq-native-pdf-structure-entry-20260829/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
