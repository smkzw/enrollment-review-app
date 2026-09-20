# Conference Participant Output: phase5-slice61ar-pdf-structure-acceptance-20260829 - general_single_object

## Boundary Check

1. **执行边界与只读约束**：本轮复核针对工作树当前最新代码与最终固化证据进行全新独立复核，全程在工作树（`.`）内以只读模式执行。未修改任何源码或测试文件，未读取工作区外原始临床资料，未直接写入受管报告路径。
2. **职责与验收权限**：本产物为独立同行技术复核意见（Advisory），不越权做出临床、法规或最终产品验收；Codex 拥有最终综合裁决与验收权力。
3. **最新查验对象与证据基线**：
   - 核心代码当前状态：`app/protocols/pdf_structure.py`、`app/evidence/pdf_native.py`、`app/evidence/page_processor.py`、`app/protocols/source_alignment.py`；
   - 专用回归测试：`tests/v2/protocols/test_source_alignment.py`、`tests/v2/protocols/test_pdf_structure_quality.py`、`tests/v2/protocols/test_pdf_structure_entry.py`、`tests/v2/evidence/test_pdf_native_coordinates.py`；
   - 最终全量验证证据：`runs/verification/phase5-slice61ar-pdf-layout-structure-quality-20260829/full-backend-tests-final.txt`（3154 passed, 3 skipped, 141 warnings, 18 subtests passed）、`mg-k10-sar-v2.1-structure-quality.json`（accepted=true, 2756/2756 bbox-aligned, 0 anomalies, 0 violations）、`d001-replay-a.txt` / `d001-replay-b.txt`（重放指纹严格一致）。

---

## Independent Work Product

本轮复核严格对照当前最新代码实现，逐项验证前序问题修复与核心质量挑战：

### 1. 已修复核心项逐项代码级验证

#### （1）碰撞豁免收紧为严格线性前缀单链（`app/protocols/source_alignment.py`）
- **代码核验**（`app/protocols/source_alignment.py:518-525`）：
  ```python
  refs = sorted(
      (item.source_ref for item in members),
      key=lambda value: (len(value), value),
  )
  if len(set(refs)) == len(refs) and all(
      child.startswith(parent + ".")
      for parent, child in zip(refs, refs[1:])
  ):
      continue
  collision_keys.add(key)
  ```
- **机制与测试验证**：
  - `len(set(refs)) == len(refs)` 防御了重复 `source_ref` 伪装；
  - `all(child.startswith(parent + ".") ...)` 强制要求按长度排序后的每一项必须是前一项的严格后代。若集合包含 `s1.t0.r0.c0.p0` 与 `s1.t0.r0.c1.p0`（兄弟分支），因后者不以前者加点为前缀，判定为 `False` 并正确触发降级为 `UNALIGNED`；
  - 对应专用回归测试 `test_collision_exemption_allows_only_one_linear_ancestry_chain`（`test_source_alignment.py:34-45`）验证通过。

#### （2）临床计量单位与时间前缀全面扩充及语境隔离（`app/protocols/pdf_structure.py`）
- **代码核验**（`app/protocols/pdf_structure.py:117-128`）：
  - 单位集合完整扩充：`kg|mg|μg|µg|ug|ng|pg|mL|μL|µL|uL|dL|mmol|mol|IU|cm|mm|min|sec|h|g|L|m|s`（配有 `(?=[^A-Za-z]|$)` 前缀界定，防御英文单词误伤）；
  - 中文时间/频次/计数词汇配有精确前瞻界定：
    - `(?:周|天|月|年|小时|分钟|秒)(?=内|前|后|以上|以下|至少|最多|不超过|[\s/]|$)|`
    - `次(?=[/\s]|每日|每周|每月|日|周|月|年|$)|`
    - `例(?=受试者|患者|病例|样本|数|[\s/]|$)|`
    - `(?:名|位)(?=受试者|患者|研究者|人员|[\s/]|$)|`
    - `%|℃`
- **机制与测试验证**：
  - 既能有效将 `10  ng/mL 维持浓度`、`20  % 受试者`、`1  次/日`、`5  mmol/L`、`96 h，药代参数` 判定为非标题；
  - 又通过严格的前瞻界定，完美保留了 `9.3 分析人群`（未匹配“分钟”）、`9.4.4.1.2  次要估计目标`（未匹配“次/日”等频次）、`例外情况说明` 等真实临床大纲标题；
  - 专用回归 `test_plain_measurements_and_time_windows_are_not_numbered_headings`（`test_pdf_structure_quality.py:35-47`）全部断言通过。

#### （3）页边多行页眉/页脚连通扩展与单页页码回落（`app/protocols/pdf_structure.py`）
- **代码核验**（`app/protocols/pdf_structure.py:133-142, 491-584`）：
  - 引入双层边距：基准重复边缘 `CHROME_EDGE_FRACTION = 0.10`，最大边缘探测上限 `CHROME_MAX_EDGE_FRACTION = 0.14`；
  - 引入有界邻域连通传递（`CHROME_CONTINUATION_GAP_POINTS = 36.0`）：只有紧邻已确认主页眉行且垂直间距 $\le 36\text{pt}$ 的高页眉行才会被传递吸收，避免误伤正文顶部段落；
  - 引入单页页码回落：`_PAGE_NUMBER_CHROME_RE` 允许符合标准页码格式（如 `第 1 页 / 共 120 页`、`1 / 1`）的行在单页或短篇文档中免除 $\ge 3$ 页的重复频次硬门槛；
  - 专用回归 `test_short_protocol_chrome_keeps_page_numbers_out_of_body`（`test_pdf_structure_quality.py:455-487`）覆盖高页眉与单页页码，均验证通过。

#### （4）表格局部消费集隔离与失配原子丢弃（`app/protocols/pdf_structure.py`）
- **代码核验**（`app/protocols/pdf_structure.py:937, 1023, 1045-1047`）：
  - `_extract_table_unit` 内部使用独立的局部 `table_consumed = set()` 记录单元格字符；
  - 仅在 `not mismatches and cells and table.rows` 成立时，才执行全局消费集提交 `consumed.update(table_consumed)`；
  - 一旦发生任何单元格失配（`mismatches > 0`），立即返回 `(None, mismatches)`，全局 `consumed` 保持零变更；
  - 对应失配表格全部字符完整保留在 `_PageLine` 中作为常规段落提取，既不会产生残缺表格块，也不会发生正文字符丢失或断裂；
  - 专用回归 `test_caption_anchored_horizontal_rule_table_restores_rows_and_merged_cell` 验证通过。

---

## Evidence And Assumptions

### 1. 三分法审计事实（Defects vs. Deferred vs. Speculative）

#### A. 当前代码中仍可复现的缺陷（Reproducible Defects）
- **复核结论**：**当前代码中不存在任何阻碍本切片验收的 High 或 Medium 级别缺陷。**
- **微小边界观察（Low/Info 级，无需阻断验收）**：
  - 若章节标题序号与文本之间采用制表符 `\t` 分隔（`3.2.1\t研究设计`），当前 `[ \u3000]+` 未包含 `\t`，该行将退化为依赖字号/粗体排版证据识别标题，而非直接解析显式大纲级别。

#### B. 显式推迟的边界与局限（Explicitly Deferred Limitations）
以下属于设计阶段已明确定义、不影响原生文字 PDF 结构对齐切片独立成立的边界：
1. **跨页大表语义拼接（Cross-page Table Stitching）**：当前遵循页原生物理边界，按页生成独立的表格根块（`p{n}.t{m}`），跨页大表的语义拼接与上下文继承按契约由下游语义层消费端处理；
2. **全宽表格打断多栏排版（Full-width Table in Multi-column Layout）**：`pdf_native.py` 的栏探测基于页级几何空隙；若页面中段存在全宽表格贯穿左右，整页按单栏阅读顺序降级处理，属于预期的保守安全策略；
3. **非标准/英文题注三线表**：`_caption_anchored_tables` 针对方案主体的中文标准题注（`表 X-X`）进行三线表恢复；无题注或非标准格式三线表回落至 pdfplumber 默认网格提取或正文流段落提取。

#### C. 未来的推测性加固建议（Speculative Future Hardening）
1. 将 `_NUMBERED_HEADING_RE` 的空白分隔字符集由 `[ \u3000]+` 扩展为 `[ \t\u3000]+`；
2. 探索将英文题注 `Table \d+` 纳入题注锚点三线表恢复通道。

### 2. 最终固化验证数据审计表

| 验证项 | 预期指标 | 最终报告实测值 (`full-backend-tests-final.txt` / `json`) | 判定 |
|---|---|---|---|
| **全量后端测试** | 全部通过，零失败 | **3154 passed, 3 skipped, 18 subtests passed (0:10:59)** | **PASS** |
| **SAR 真实方案 (120页)** | 结构提取完成，零异常 | **2756 块（2708 段落、48 表格、158 标题），anomalies: []** | **PASS** |
| **下游对齐精度** | 100% 达到 bbox 精度 | **aligned: 2756, degraded: 0, unaligned: 0, precision: bbox (100%)** | **PASS** |
| **源工件不可变性** | 提取过程零篡改 | **source_bytes_unchanged: true, source_mtime_unchanged: true** | **PASS** |
| **两次提取确定性** | 独立运行哈希一致 | **runs_identical: true (`08a3541bfad9496fcb...`)** | **PASS** |
| **重放包指纹** | 重放校验通过且一致 | **`d001-replay-a.txt` == `d001-replay-b.txt` (`cdb75fbc...`)** | **PASS** |
| **解码器版本迁移** | 干净切换至 v2 | **`DECODER_VERSION_BY_KIND["pdf"] == "slice61ar/pdfplumber/v2"`** | **PASS** |

---

## Risks, Gaps, And Verification Needs

1. **结构质量与对齐契约完备**：Phase 5.8d 原生文字 PDF 结构提取切片已全面满足排版分块、标题层级恢复、三线表及跨列合并单元格保序切片、页眉页脚精确隔离、确定性内容寻址与下游不可变工件对齐要求；
2. **门禁与回归无死角**：新增的线性前缀碰撞校验、临床计量单位语境前瞻、多行高页眉连通和表格原子消费机制均已具备强针对性的单元与集成回归测试覆盖；
3. **验收风险已消除**：不存在未闭环的严重缺陷或回归隐患。

---

## Recommended Next Step

1. **建议裁决**：经本轮针对最新代码与最终证据的全面复核，确认**无任何 High 或 Medium 级别阻断性问题**，Phase 5.8d 原生文字 PDF 结构质量切片已达到交付标准；
2. **主会场操作**：建议 Codex 予以正式验收合入，推进主会场交付物归档及后续 Phase 5 临床事实与 Patient Profile 业务流衔接。
