# Phase 4 外部方案核查

## 要解决的问题

Phase 4 必须同时保存可复核的原文、页图、OCR 文本和真实定位精度。实现不能因为某个 OCR 模型输出了 Markdown，就把没有坐标的文本伪装为页内精确定位。

## 核查结果

### 1. 原生 PDF 坐标

- 项目正式依赖已固定 `pdfplumber==0.11.10`。其官方仓库说明可以读取字符、矩形、线条等 PDF 对象，并采用 MIT 许可证：
  - https://github.com/jsvine/pdfplumber
  - https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt
- PyMuPDF 可返回单词坐标且速度较快，但官方仓库明确采用 AGPL-3.0 或商业许可：
  - https://github.com/pymupdf/PyMuPDF
- 结论：V2 正式路径使用 `pdfplumber` 获取原生 PDF 字符/词坐标；不把当前仅在开发依赖中的 PyMuPDF 引入 V2 运行路径。若后续性能证明不足，再单独做许可证和替代方案评估。

### 2. 扫描页和照片的布局识别

- PaddleOCR-VL 官方文档说明完整流水线包含“布局分析 + 元素裁剪 + VLM 识别 + 阅读顺序合并”；只调用 VLM 推理服务并不等于完整文档解析：
  - https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL.html
  - https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/PaddleOCR-VL-Apple-Silicon.html
- 官方流水线支持 `rect / quad / poly` 布局坐标，并支持队列化的 PDF 页面渲染、布局和 VLM 推理。PaddleOCR 仓库采用 Apache-2.0：
  - https://github.com/PaddlePaddle/PaddleOCR
- 结论：保留现有 oMLX VLM 适配器作为文本识别能力，但 Phase 4 必须先做完整 PaddleOCR-VL 布局输出能力 spike。只有 sidecar 确实返回与页图一致的坐标时才能形成 `bbox`；否则按 `text_range / page_excerpt / page_only` 诚实降级。

### 3. 不采用项

- 不引入 OCRmyPDF：它适合生成可搜索 PDF 和 hOCR sidecar，但本阶段需要的是不可变原文件、独立页图、版本化 OCR 结果和证据定位，不需要改写或重建用户 PDF。
- 不把模型 Markdown 直接作为 EvidenceSpan：Markdown 是识别结果，不是来源坐标或页内唯一锚点。

## 决策

1. 原生 PDF：`pdfplumber` 字符/词坐标，输出统一页坐标合同。
2. 扫描页/照片：完整 PaddleOCR-VL 布局能力 spike；现有 oMLX 文本通道继续作为可替换识别后端。
3. 缓存身份：文件 SHA-256 + 页码 + OCR 模型标识 + 参数规范化哈希 + 适配器版本。
4. 定位精度：由确定性定位器判定，Agent 无权提升精度。
5. 若布局 spike 失败，Phase 4 仍可发布 `text_range / page_excerpt / page_only`，但必须保存降级原因并在界面可见。

## 回滚

布局适配器通过接口隔离。若完整 PaddleOCR-VL 在本机环境不稳定，可关闭布局能力并回到现有 oMLX 文本识别；已保存的原文件、页图、原 OCR 和低精度 EvidenceSpan 不受影响。
