# Phase 3 文档解析路线调研

## 真实输入观察

### MG-K10-SAR V2.1

- DOCX 约 418 KB，21 个 section、1317 个正文段落、26 个顶层表格。
- 页眉直接包含方案编号 `MG-K10-SAR-001` 和 `V2.1//2025年09月19日`，比正文通用标题更可靠。
- 方案同时包含 II/III 期内容，并明确写有“操作无缝”；入选标准按期别分段，排除标准为两期共享。
- 旧提取器在 III 期得到 IN 7、EX 16，但研究流程表返回空节点。

### D001 V1.0

- DOCX 约 406 KB，10 个 section、1263 个正文段落、24 个顶层表格。
- 页眉同时包含模板文件编号/版本和真正的方案编号/版本，必须按标签上下文区分，不能看到第一个“版本号”就采信。
- 正文和流程表分别描述 II、III 期；旧提取器在 II 期得到 IN 6、EX 30，但研究流程表同样返回空节点。
- 文件名日期与正式页眉日期不一致，正式字段优先，文件名只能兜底。

## 候选方案

### A. 继续使用 python-docx，并补直接 OOXML 读取

- `python-docx` 1.2.0 已在项目中使用，MIT 许可；可读取段落、顶层表格、section、页眉页脚。
- 对嵌套表格、编号定义、修订标记、域代码和文档部件使用受控 OOXML 读取补足。
- 优点：依赖小、行为可控、适合把“官方编号”和“页眉身份字段”做成确定性结构提取。
- 局限：DOCX 本身没有稳定分页坐标；Word 渲染页码不能仅靠 OOXML 推断。

### B. Docling / docling-slim

- 官方项目为 MIT 许可，支持 DOCX、文档层级、表格、页眉页脚和 provenance 结构。
- 优点：统一文档模型成熟，可能减少自建通用结构树的工作量。
- 局限：DOCX 的页级坐标“如可用”才存在；仍需额外渲染建立真实页级定位。依赖和抽象层明显更重，且不能替代本项目针对官方编号、期别和临床逻辑的确定性门禁。
- 决策：不在主路径直接引入。实施第一步用两份真实方案做一次隔离 spike；只有结构保真和运维成本明显优于现有路线时才采用，否则记录拒绝理由后停止评估。

### C. LibreOffice 无界面渲染 + PDF 文本坐标

- 本机已安装 LibreOffice 26.2.5.2；官方 CLI 支持 `--convert-to pdf`。
- 渲染后的 PDF 可提供稳定的本次渲染页码和文本坐标，但必须记录渲染器版本、输出哈希和“渲染页”语义，不能冒充原作者环境中的绝对分页。
- 项目当前使用 PyMuPDF，但其 AGPL/商业双许可不适合作为未来可复用商业子系统的新依赖决策基线。
- `pdfplumber` 为 MIT 许可，可读取页、字符/词坐标和文本搜索；拟在 spike 中与现有 PyMuPDF 结果比较，满足定位精度后再决定是否锁定依赖。

## 选择

采用双通道来源模型：

1. **结构通道**：python-docx + 受控 OOXML，保留文档部件、段落/表格顺序、编号层级、section、页眉页脚和原文。
2. **渲染通道**：固定版本 LibreOffice 生成只读 PDF 派生物，再建立渲染页和文本范围定位。
3. 两通道通过规范化文本片段和稳定 source_ref 对齐；对齐失败时降级到文档部件/段落定位并明确标识，不伪造页码或坐标。
4. Docling 仅作为有停止条件的候选 spike，不成为 Phase 3 开工前提。

## 决策依据来源

- python-docx 页眉页脚说明：https://python-docx.readthedocs.io/en/latest/dev/analysis/features/header.html
- python-docx MIT 许可：https://github.com/python-openxml/python-docx/blob/master/LICENSE
- LibreOffice PDF CLI 参数：https://help.libreoffice.org/latest/en-US/text/shared/guide/pdf_params.html
- Docling 文档结构与 provenance：https://docling-project.github.io/docling/concepts/docling_document/
- Docling MIT 包声明：https://github.com/docling-project/docling/blob/main/pyproject.toml
- pdfplumber 坐标与 MIT 项目：https://github.com/jsvine/pdfplumber
- PDF 库许可对比：https://github.com/py-pdf/benchmarks

## 剩余验证

- 用 MG-K10-SAR、D001 各抽取页眉、第一页、入排章节、流程表和随机前要求，比较三个候选的结构完整性和耗时。
- 检查 LibreOffice 渲染字体替换、页数和正文定位稳定性；把渲染器版本写入派生物 manifest。
- 验证修订标记、嵌套表格和 Word 自动编号能否完整保留；失败时必须停止发布而非退化为空结果。

## 切片 1 实测结论（2026-08-14，worker_03 验证）

### pdfplumber spike —— 采纳

在隔离 venv 安装 `pdfplumber==0.11.10`（依赖链 pdfminer.six/pillow/pypdfium2 均为
MIT/BSD/Apache-2.0 许可，无 AGPL），用 LibreOffice 26.2.5.2 渲染两方案后与 PyMuPDF 1.26.4 对比：

| | MG-K10-SAR（221 页） | CMS-D001（169 页） |
|---|---|---|
| 页数（PyMuPDF vs pdfplumber） | 221 = 221 | 169 = 169 |
| 对齐 aligned（PyMuPDF → pdfplumber） | 403 → 576 | 517 → 666 |
| 对齐 unaligned（PyMuPDF → pdfplumber） | 1623 → 1272 | 1464 → 1206 |

结论：页数完全一致；来源对齐「未命中」块在两份方案上分别减少 351 / 258，
pdfplumber 文本更干净，显著改善定位。**采纳**：`app/protocols/rendering.py` 的
`pdf_page_count`/`pdf_page_texts` 已替换为 pdfplumber，并 pin `pdfplumber==0.11.10`
入正式运行依赖组（方案渲染模块在运行时直接导入）。PyMuPDF 仅由遗留管线
（`app/pipeline/*`）继续使用，不在本切片范围。

### 切片 1 验收后的页定位边界

- 精确页定位采用保守策略：跨页和页内均唯一、页内范围可回验、且不同结构块不共享
  同一物理范围时，才保留 `TEXT_RANGE`；表格仅在信息量最高的候选文本唯一命中时
  保留 `PAGE_ONLY`。页眉页脚只作降级页面提示。
- 两份真实方案曾分别发现 48/64 个结构片段共享物理范围；跨 span 唯一性后处理已将
  其全部降级，独立复测剩余碰撞为 0/0、页级核验失败为 0/0。
- 诚实拒绝后，MG-K10-SAR 与 D001 仍分别有约 1954/2120 个非空正文段落无可靠页。
  这是页级召回限制，不是规则文本丢失。切片 3 前做带逆序检测和窄页差门槛的邻块
  插值 spike；插值页只能作提示，不得单独满足发布来源门槛。

### Docling —— 不安装（拒绝）

未安装 Docling。结构通道（python-docx + 受控 OOXML）已覆盖 Docling 能带来的
结构不变量：嵌套表格完整祖先路径、样式继承的自动编号、default/first/even 页眉
角色保留、修订标记计数；而 Docling 的 DOCX 页级 provenance「如可用才存在」，
仍需 LibreOffice 渲染建立真实页级定位，故无决定性结构增益，且依赖显著更重。
不写入项目依赖。

### MG-K10-SAR 未解析编号人口调查

旧实现把 637 个直接编号段中「未解析出抽象编号」的 17 段当作未解析；实测这
17 段全部是 `w:numId=0`（OOXML 表示「显式取消编号」），并非悬空引用。真正的
「numId 非 0 却无法映射到抽象编号定义/级别格式」的未解析编号为 **0** 段。

- 620 个直接 `numId` 段全部解析成功；另有约 137 个章节标题段通过段落样式
  （style 1/2/3/4/5 → numId 1）继承编号，此前被静默丢弃，现已还原。
- 入选/排除父规则（`入选标准`/`排除标准` 标题为 style=2，条目用直接 numId 36/42/43…）
  全部解析成功，**无任何官方 IN/EX 父条目受未解析编号影响**。

实现：`numId=0` 返回「无编号」（非异常）；样式继承编号沿 `w:basedOn` 链还原；
`numId` 非 0 却无法解析时产出 `unresolved_numbering` 提取异常并把状态置
`needs_review`，绝不静默丢弃编号上下文。
