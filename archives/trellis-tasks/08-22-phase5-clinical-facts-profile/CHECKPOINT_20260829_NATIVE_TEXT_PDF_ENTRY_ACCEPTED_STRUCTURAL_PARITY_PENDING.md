# Phase 5.8d 原生文字 PDF 入口验收，结构等价待续

Date: 2026-08-29

## 本轮目标

使用未经用户预处理的原生文字 PDF，进入与 DOCX 共享的 `StructureBlock` / `ProtocolExtractionSnapshot` / 来源定位链。本轮只验收输入、身份、文本块和精确页面定位，不宣称 PDF 的标题、编号、表格或多栏阅读顺序已与 DOCX 等价。

## 已接受

- 按文件魔数分派 DOCX/PDF，禁止纯文本回落。
- PDF 原始哈希、物理页号、文本区间和字符坐标框进入冻结块；对齐前重新逐字核对页文本区间，不匹配即拒绝伪精确。
- PDF 直接复用原文件作为页面载体，不经 LibreOffice 二次转换。
- 扫描、部分页无文本层、零页、加密、损坏和哈希不一致均失效关闭，不调用 OCR 或模型猜测。
- 加密 PDF 现可穿透 `pdfplumber` 异常包装识别，不再误报为损坏文件。
- DOCX 块不序列化未使用的 PDF 定位字段，D001 冻结指纹保持 `cdb75fbc9812940acf2048a44ef28455a3b3111af57611ed81ac055db21d61d3`。

## 可复现证据

- 聚焦回归：`12 passed, 5 warnings`。
- 后端全量：`2977 passed, 1 skipped, 139 warnings, 2 subtests passed`；跳过项为既有 oMLX 探针工件缺失。
- 真实 SAR V2.1 PDF：120 页、285 块，两次内容哈希均为 `7843e5e55966da24044b224e2221418d3d838bcf819cf557824702ca4ad726c3`；285/285 直接 bbox 对齐，0 降级，0 未对齐；源文件字节和 mtime 不变。
- 证据目录：`runs/verification/phase5-slice61aq-native-pdf-structure-entry-20260829/`。
- 执行审计通过；独立 CodeBuddy / DeepSeek V4 Flash max 审查意见已逐项处置。

## 未接受与下一安全步骤

- PDF 多栏正文、边栏、表格和表单可共用大水平间距特征；本轮不用单一启发式误报整份方案。
- 下一独立质量切片应同时处理版面分区、栏阅读顺序、标题层级、表格结构和空白页/图像扫描页分流，使用真实方案反例独立验收。
- PDF 身份页面工件的完整领域清单、面向用户的加密/损坏精细恢复文案可随上述质量切片一并收口。

## 边界

本轮没有调用临床 LLM/VLM，没有发布方案控制点，没有处理受试者、OCR、Patient Profile 或审核结论。D001 v8 仍是已拒绝反例，`claims_complete=false`，Phase 5 未完成。
