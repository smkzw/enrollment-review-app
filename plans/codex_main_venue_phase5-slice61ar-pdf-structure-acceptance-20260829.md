# Codex Main-Venue Plan: phase5-slice61ar-pdf-structure-acceptance-20260829

Date: 2026-08-29
Objective: 只读独立复核 Phase 5.8d 原生文字 PDF 结构质量切片。审查当前工作树中的 app/protocols/pdf_structure.py、app/evidence/pdf_native.py、app/evidence/page_processor.py、app/protocols/source_alignment.py、相关 tests/v2/protocols 与 tests/v2/evidence、scripts/verify_pdf_structure_quality.py，以及 runs/verification/phase5-slice61ar-pdf-layout-structure-quality-20260829 中的固化报告。重点挑战：通用标题识别是否误把数值/时间窗当标题；横线表格及合并单元格是否保持页原生顺序和精确来源范围；页眉页脚是否隔离正文；祖先/后代范围重叠豁免是否会放过无关重复；解码器版本迁移与测试隔离是否正确；真实报告、全量测试和结论是否匹配。不得修改文件，不得读取工作区外原始临床资料，不得自行声称最终接受。输出按严重度列问题、证据、建议和有限结论。

## Task Decomposition

1. 核对当前 PDF 结构提取、来源对齐和解码器版本代码。
2. 核对标题、临床单位、页眉页脚、横线表格和范围碰撞回归。
3. 复查真实 SAR PDF 固化报告、D001 双重放和后端全量测试。
4. 对首轮审查问题修复后在同一会话复核，并由 Codex 独立裁决。

## Source Packet

- 当前工作树中的实现与回归测试。
- `runs/verification/phase5-slice61ar-pdf-layout-structure-quality-20260829/` 固化证据。
- 真实 SAR V2.1 PDF 仅用于 Codex 本地验收；会商者未读取工作区外原始资料。
- D001 重放只验证既有 DOCX 链不漂移，不代表 D001 临床解构完成。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `general_single_object` | `google-antigravity` | `gemini-3.7-flash` | `runs/conference/phase5-slice61ar-pdf-structure-acceptance-20260829/general_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

- 首轮完成后提出 1 项高等级、3 项中等级及 1 项低等级问题；均由 Codex 核验后修复。
- 第二轮续问未带入修复证据，重复审阅旧状态，不用于最终结论。
- 第三轮在同一会话中明确提供当前代码和最终证据，完成 54.268 秒，无 fallback；其结论纳入验收。

## Codex Verification Checklist

- [x] 当前代码逐项核对首轮问题的闭环实现。
- [x] 聚焦回归 `83 passed`，最终后端全量 `3154 passed, 3 skipped`。
- [x] 真实 SAR PDF 两次提取一致，2756/2756 坐标级对齐，源文件未改变。
- [x] DOCX/PDF 正文标题归一化对照：DOCX 154 项全部在 PDF 中出现。
- [x] D001 两次模型无关重放指纹一致。
- [x] `compileall` 与 `git diff --check` 通过。
- [x] 明确区分本切片接受、扫描/混合 PDF 延后、临床控制点未发布。
