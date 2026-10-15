# Slice 4.0 能力金标准与坐标 spike 决策记录（实测）

日期：2026-08-19  |  工作树：`phase4-evidence-ocr-v2`  |  只读合成样本，无 PHI

## 1. 金标准
- 名称：`slice4.0-synthetic`；页面 26 页；文件 23 个。
- 覆盖：原生 PDF（唯一/跨行/表格/重复文本）、扫描 PDF、照片、TXT(UTF-8/GB18030)、多页 TIFF、DOCX、失败页（截断 PDF、无效 .doc、损坏图片）。
- 确定性：PDF trailer `/ID` 的十六进制和 literal-string 两种序列化均规范化为固定值；跨进程重复生成由回归测试复核。
- 文件内容 SHA-256：

  - `bad-image-01.png` = `147474249745a43f48c18c925f0c4bd0e6213f40474a8b89d7cd261101711685`
  - `corrupt-01.pdf` = `d4aa4dc6b0bfd40493f0a064ffbb7c9c3350eb333bfd6c48f686b42678c2edab`
  - `docx-01.docx` = `b68520737ec7b99fe849711b021dc95095e89d4205121c8623aa2823f90f4052`
  - `multi-01.tiff` = `649778fd79d95aed46e0a0ab28fd4eed9f510e42fcb25b490804e67f2c1ff910`
  - `native-01.pdf` = `2c640e5a5dda9545c26194ba59ea856545c7e64cd1e681f8883e41ed1a4e8165`
  - `photo-01.jpg` = `b34ed0d3c4978a2b928763ed5a1f57a7e932f62d528726c40bea6f56ff021d56`
  - `risk-clean-01.txt` = `b1baa04bd485f1682aaa3649ee20fbb9d03373cb6bd25636306364533bc963bf`
  - `risk-clean-02.txt` = `8f859333b54fb6840dafb2d5b63d154069afcd7ddd4f847a09e20c77929a4cb0`
  - `risk-clean-03.txt` = `b5345d59053cdeb05dff92b939e4d0a000f3054faa04e77e07923c39f94d6960`
  - `risk-clean-04.txt` = `54848655ba9c12e2b2e47c867c044129095893734fb461c53f61eca94cbe3606`
  - `risk-clean-05.txt` = `a9bb35e1520842c54539e24ef616d1460e1a89ad04a8e84302ba277a5677f5d1`
  - `risk-clean-06.txt` = `8151d139a996fa4c8cf04ba9105302ff68cca3619c9d4621331d7f566f621ac1`
  - `risk-clean-07.txt` = `169b0b37701fab8ac0655d2cd85d59324947400e8de25723e72ffda47c12721f`
  - `risk-clean-08.txt` = `231d7d9f10ed5cf7276c0d9a11f7f0ef0b63c0f4d5433c70ce75f69444f989a2`
  - `risk-clean-09.txt` = `bb332929e66da8b0e13aeba8a59b73a14c46e7f2d97d149c38271ace28cd2ebb`
  - `risk-clean-10.txt` = `117db4524a2c0d3475cbadb5dd3b47b38ea441faa23b33d1790bdb3809832726`
  - `risk-clean-11.txt` = `dec0a4f5c3aba894b3cf36bb0e820735169f5bd76815263c302878b9dca586b8`
  - `risk-clean-12.txt` = `6f8255306cdc4cfd4de2e564278b29046bf853c54ba29a8292776bb2b2f3fb01`
  - `risk-clean-13.txt` = `061951aece3dd9e24bf0e892eb7db07c1a9b7b38cdc9279aa761692485c5cd68`
  - `scanned-01.pdf` = `14183bcc12a0ef1630776e6678aa722a0042467bca536fdf83df31fb3a289740`
  - `txt-01.txt` = `803f58ffed65cab2a9b1ac53f294b1371fbfb219ddb6801dc77a23fc3a93d71b`
  - `txt-gb18030.txt` = `52e6b0a540264569a3106bc561c6f7970d64ed8fd09876671ed8536ab12d0944`
  - `unsupported-01.doc` = `e86546a49aeb27b5a2dbad42f53900d78a728bfc507bdb120d8ff5227c1842b4`

## 2. 原生 PDF 文本回读一致率
- 结果：18/18 = **100.0%**（门槛 ≥100%）→ 通过
- 失败页：无

## 3. 目标定位成功率（pdfplumber 原生坐标）
- 结果：7/7 = **100.0%**（门槛 ≥95%）→ 通过
- 失败：无

## 4. pdfplumber 坐标 -> 渲染页图像素 spike
- 映射 bbox：5 个；页内边界通过 5/5。
- 与真实绘制区域 IoU：min=0.8333, avg=0.8333；≥0.5 达标 5/5。
- 逐目标映射：

  - native-01-p1 `否认高血压病史` pdf_bbox=[128.0, 719.2, 226.0, 733.2] -> pixel_bbox=[266.67, 226.67, 470.83, 255.83] img=[1240, 1755] in_bounds=True iou=0.8333
  - native-01-p1 `76.1` pdf_bbox=[296.0, 719.2, 352.0, 733.2] -> pixel_bbox=[616.67, 226.67, 733.33, 255.83] img=[1240, 1755] in_bounds=True iou=0.8333
  - native-01-p1 `2026年3月14日` pdf_bbox=[254.0, 749.2, 394.0, 763.2] -> pixel_bbox=[529.17, 164.17, 820.83, 193.33] img=[1240, 1755] in_bounds=True iou=0.8333
  - native-01-p2 `36.5` pdf_bbox=[184.0, 679.2, 240.0, 693.2] -> pixel_bbox=[383.33, 310.0, 500.0, 339.17] img=[1240, 1755] in_bounds=True iou=0.8333
  - native-01-p3 `32.5` pdf_bbox=[114.0, 719.2, 170.0, 733.2] -> pixel_bbox=[237.5, 226.67, 354.17, 255.83] img=[1240, 1755] in_bounds=True iou=0.8333

## 5. 扫描/照片布局候选度量机制
- 合成候选定位成功率（度量机制验证，非真实解析器）：6/6 = **100.0%**（门槛 ≥90%）。
- 候选来源：`synthetic_gold_geometry_metric_demo`；该结果只证明度量机制，不证明任何 OCR/布局解析器能力。
- 页错位：无；越界：无；文本不匹配：无；覆盖失败：无。
- 结论：布局候选 >=90% 且区域均在正确页并覆盖目标的度量**机制**成立；
  本次门禁选择 GLM 的文字探针未返回机器坐标，因此不采用扫描/照片布局红框；不得以本合成度量冒充布局能力验收（见 `slice4-omlx-gate-probe.md`）。

## 6. 风险种子集（Slice 4.0 冻结矩阵）
- 原生 PDF/TXT 风险输入来自实际解码文本；扫描/照片/TIFF/DOCX 使用独立编写的合成期望文本，仅验证确定性风险规则，不代表 OCR 推理实测。
- 关键风险漏检：0 / 26（要求 0）→ 通过。
- 页面级误报：0/13 干净页 = **0.0%**（≤10%）→ 通过。
- 覆盖：已处理 23/23 页，未处理页：无。
- 参与页：风险页 10，干净页 13。

## 7. 采用/拒绝路径、许可证与诚实降级结论
- 原生 PDF 正式坐标路径：`pdfplumber==0.11.10`（MIT，项目已固定）。本 spike 实测字符/词坐标可回读、可换算到渲染页图像素并对照真实绘制区域。
- 扫描/照片/多页 TIFF：只建立布局候选度量与真实绘制区域对照机制；**未**断言任何 VLM 布局模型已采用。
- 诚实降级：`bbox > text_range > page_excerpt > page_only`；重复文本未稳定消歧必须降级并说明原因，本金标准已包含重复文本降级反例。
- 风险矩阵冻结：极性/数值/小数点/单位/日期 = 阻断（未核对阻止激活）；重复文本/低置信 = 提示（不阻断）。

## 8. 总门禁
- 回读 ✔ | 原生定位 ✔ | 布局度量机制 ✔（不等同采用） | 风险漏检 ✔ | 风险误报 ✔ | 风险覆盖 ✔ | 布局采用 ✘（真实探针无坐标）。

## 9. 下一步
- Slice 4.1：本次复核不实施；门禁选择 GLM 的文字探针已完成，坐标路线拒绝采用。主控可在既有用户批准边界内另行开启 4.1，但当前树的 4.1 ORM 表尚未有迁移，不能据此记录放行。
- 扫描/照片：门禁文字路线仅在本合成能力样本范围内采用；模型实际加载身份未由独立服务清单证明；布局坐标路线拒绝采用。
