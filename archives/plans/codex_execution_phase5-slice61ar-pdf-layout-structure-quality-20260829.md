# Codex Execution Plan: phase5-slice61ar-pdf-layout-structure-quality-20260829

Objective: 修复原生文字型研究方案 PDF 的结构质量：在不改源文件、不写死项目规则、不破坏已验收页码/文本范围/bbox/哈希契约的前提下，区分空白页与扫描页，恢复稳定的版面阅读顺序、标题层级和表格结构，使真实 SAR/D001 方案可用于全文覆盖清单和后续控制点解构；用确定性测试与真实方案证据验收。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计现有 pdf_native/pdf_structure、StructureBlock 契约、真实 SAR PDF/DOCX 差异和 PyMuPDF/pdfplumber 能力，提出最小通用实现方案、风险与验收矩阵；不得修改文件。 | `runs/execution/phase5-slice61ar-pdf-layout-structure-quality-20260829/worker_01.md` |
| `worker_02` | 实现通用 PDF 页面分类与版面结构恢复，重点处理多栏阅读顺序、表格区域/单元格、标题排版证据、空白页与扫描页分流；保留精确来源定位和失败关闭，不使用项目特异文本规则。 | `runs/execution/phase5-slice61ar-pdf-layout-structure-quality-20260829/worker_02.md` |
| `worker_03` | 补齐 PDF 结构质量的确定性回归测试与真实方案核验脚本/证据，覆盖双栏、表格、标题、短页、空白页、扫描/混合页、旋转页、确定性和源文件不变，并检查下游结构分发兼容性。 | `runs/execution/phase5-slice61ar-pdf-layout-structure-quality-20260829/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
