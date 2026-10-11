# Execution Output: phase5-slice58e-phase-reference-vs-applicability-20260825 - worker_01

## Boundary And Context Check

仅执行正文/表格期别上下文审计；未修改工作区文件、未启动会商、未读取网络或同伴报告。

D001 使用工作区只读副本，SHA-256：

`362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98`

任务中的 p9、p20、p24、p28、p33按结构引用解析为：

`body.t4.r4.c1.p9/p20/p24/p28/p33`

该单元内 `p1` 是Ⅱ期标题，`p19` 是Ⅲ期标题，正好对应任务要求的期别模式。

## Work Performed

审计了：

- `app/protocols/phase_detection.py`
  - `_scope_from_text`
  - `_body_contexts`
  - `_effective_table_scopes`
  - `project_single_phase`
- D001 只读结构提取与期别图。
- 正文、表格单元格及显式共享声明的合成反例。
- 现有结构期别回归测试。

核心缺陷：

- `_scope_from_text()` 在继承上下文前，先根据普通文本中的 `Ⅱ期/Ⅲ期` 词命中返回局部 scope。
- `_effective_table_scopes()` 明确规定“local phase mention always wins”，因此表格单元格中的对侧期别引用会覆盖已有单元格上下文。
- `_body_contexts()` 当前只能避免普通引用清除后续上下文，不能修正当前普通段落自身的适用期别。

因此“期别引用”被错误地当成“期别适用性”。

## Artifacts And Evidence

D001 提取结果：

- 3,556 个正文段落
- 25 个表格
- 3,581 个结构块
- 无提取异常
- 当前期别图：3,405 个节点

D001 目标单元当前结果：

| 来源 | 文本语义 | 当前 scope | 应有 scope |
|---|---|---:|---:|
| `body.t4.r4.c1.p9` | Ⅱ期期中分析，但末尾提到建议Ⅲ期剂量 | `MIXED` | `Ⅱ期` |
| `body.t4.r4.c1.p20` | Ⅲ期计划引用Ⅱ期完成入组及剂量结果 | `MIXED` | `Ⅲ期` |
| `body.t4.r4.c1.p24` | Ⅲ期基础期随机，引用Ⅱ期期中分析结果 | `Ⅱ期` | `Ⅲ期` |
| `body.t4.r4.c1.p28` | Ⅲ期剂量调整注释，引用Ⅱ期结果 | `Ⅱ期` | `Ⅲ期` |
| `body.t4.r4.c1.p33` | Ⅲ期扩展期安慰剂转组，引用Ⅱ期分析及Ⅲ期剂量 | `MIXED` | `Ⅲ期` |

投影影响：

- 当前Ⅱ期投影错误纳入 `p24/p28`。
- 当前Ⅱ期投影错误排除应保留的 `p9`。
- 当前Ⅲ期投影排除 `p20/p24/p28/p33`，造成Ⅲ期结构内容缺失。

合成反例：

- Ⅲ期结构标题后，普通段落“与Ⅱ期临床研究试验一致”：
  - 当前段落：`Ⅱ期`
  - 后续段落：`Ⅲ期`
  - 应为：当前段落也属于`Ⅲ期`，但保留Ⅱ期引用证据。
- 表格单元格内Ⅲ期标题后，普通段落“根据Ⅱ期研究结果调整剂量”：
  - 当前段落：`Ⅱ期`
  - 应为：`Ⅲ期`。
- 真正的表格单元格标题从Ⅱ期切换为Ⅲ期：当前行为正确。
- 明确“Ⅱ期和Ⅲ期均采用相同标准”的共享声明：当前行为为`SHARED`，应保留。
- 无任何结构上下文时，普通期别提及可以作为本地候选，但不得向后传播；当前行为符合这一边界。

当前测试 `tests/v2/protocols/test_metadata_phase_slice2.py` 为 `25 passed`，但其中两处断言编码了旧语义：

- `test_local_phase_mention_does_not_clear_existing_structural_context` 将上下文内普通Ⅱ期引用断言为Ⅱ期。
- `test_same_table_cell_phase_headings_switch_only_the_local_tail` 将Ⅱ期上下文内普通Ⅲ期引用断言为Ⅲ期。

这两处只验证“不会改变后续上下文”，未验证“当前单元的适用期别应由上下文支配”。

建议定义：

- 期别引用：文本中提到另一期的比较、历史结果、剂量依据、阶段转换、交叉引用或下游建议。
- 期别适用性：该结构单元实际执行/描述的研究期别。
- 结构标题、表格单元格期别标题、明确适用性引导句可以切换适用范围。
- 明确两期共同/相同适用声明可以切换为`SHARED`。
- 普通叙述中的期别引用不得覆盖已有正文章节、表格单元格、行列或表级上下文。
- 原文文本和引用证据必须保留，不能通过删除对侧期别词来伪造单一期别文本。

## Commands And Observations

- 读取执行上下文与计划：确认本 worker 为只读审计。
- 读取 D001 工作区副本并计算 SHA-256：与既有 D001 哈希一致。
- 使用 `.venv/bin/python` 执行 DOCX 结构提取及期别图构建：成功。
- 执行：

  `.venv/bin/python -m pytest -q tests/v2/protocols/test_metadata_phase_slice2.py`

  结果：`25 passed in 0.02s`。
- 尝试使用应用渲染器生成 PDF：LibreOffice 退出码 `134`，发生 `Abort trap: 6`。未产生可用 PDF。

## Blockers Or Missing Environment

LibreOffice 当前在本机渲染 D001 时崩溃，因此未完成新的 PDF 视觉/页码对齐。该阻塞不影响本次基于 DOCX 结构块和已有来源定位的期别传播审计。

未修改任何工作区源文件或测试文件；实现和回归更新不在本 worker 授权范围内。

## Rerun Requests Or Next Step

请 Worker 02：

1. 在已有清晰结构上下文时，令普通段落/表格单元格的有效适用期别优先继承上下文。
2. 仅允许真正期别标题、明确适用性引导句、明确共享声明切换范围。
3. 独立保留对侧期别引用，不将其压入 `MIXED` 或改写原文。
4. 补充 D001 风格的正文和表格单元格反例。

请 Worker 03：

1. 将 D001 `body.t4.r4.c1.p9` 修复为Ⅱ期。
2. 将 `p20/p24/p28/p33` 修复为Ⅲ期。
3. 重新量化全文单元、投影和批次，并核对 MG-K10 回归。
4. 更新上述两处过时合成断言后再运行结构期别测试。
