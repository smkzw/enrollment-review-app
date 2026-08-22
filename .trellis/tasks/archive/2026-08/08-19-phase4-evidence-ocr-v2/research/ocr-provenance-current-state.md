# Research: Legacy OCR and provenance current state

- Query: 研究 legacy OCR 与来源定位能力，判定可封装复用边界、V2 核心禁入项，核对 8 路并发/缓存/页图/原生 PDF 文本与 word box/风险校对真实能力，并给出内容哈希缓存与 EvidenceSpan 精度 spike 的最小可验证方案。
- Scope: internal
- Date: 2026-08-19

## Findings

### 结论摘要

1. **可复用的是能力，不是 legacy 数据模型或管线。** 可以封装页渲染、oMLX/OpenAI-compatible 调用、单进程内 8 路 VLM 准入、原生 PDF 文本提取和纯风险检测；但必须换成结构化输出、不可变工件、持久 Job 和诚实定位降级。
2. **“8 路”当前只是同一 Python 进程、同一 event loop 内的 VLM 调用上限，不是跨进程全局上限。** 测试仅使用 mock VLM 证明两批并发时峰值为 8，未证明真实 oMLX 在 8 路下的吞吐、内存、超时或完整性。
3. **现有缓存不满足 Phase 4。** PDF 主路径只要 `<stem>/pN.md` 存在且大于 10 字节就命中，不检查源文件、模型、prompt、DPI 或解析器版本；图片/DOCX/TXT 仅依赖 mtime。
4. **页图只是不完整的中间缓存，不是来源工件。** 扫描页和被高风险复核的原生 PDF 页会写 JPEG；普通原生 PDF 页、DOCX/TXT 没有页图。当前没有页图 manifest、哈希、坐标系或稳定的查看 API。
5. **原生 PDF 只有 plain text，没有 word box。** 已引入 PyMuPDF 1.26.4，但 legacy 仅调用 `page.get_text()`；设计文档所说的 word box 尚未实现。
6. **oMLX 当前只返回纯文本，并主动删除 LOC token。** 因此现有调用链不能支持 bbox 承诺；oMLX 布局输出必须先做保留原始响应的能力 spike。
7. **风险校对是“提示 + 二次 OCR”，不是确定性校对。** 它能触发否定词/时间窗复核、检测重复幻觉，但不对否定词、小数、单位、日期做结构化差异，也不产生 CorrectionRecord。幻觉处理还会将去重/截断后文本直接写入缓存，不符合“保留原 OCR”。

### 文件与作用

| 路径 | 作用 |
|---|---|
| `plans/REARCHITECTURE_IMPLEMENTATION_PLAN_20260812.md` | Phase 4 工作项与退出门槛，包括内容哈希缓存、8 路 OCR、页图和定位 spike（:123-142）。 |
| `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` | OCRPage/EvidenceSpan 目标、精度阶梯、word box 目标、持久 Job 和 legacy 保留/淘汰边界（:74-83, :114-136, :384-394, :404-438）。 |
| `docs/REARCHITECTURE_DISCOVERY_20260812.md` | legacy 已有能力与审计缺口：最多 8 路、mtime 缓存、无坐标，以及“保留并封装”原则（:66-77, :110-115, :258-279）。 |
| `.worktrees/phase4-evidence-ocr-v2/.trellis/tasks/08-19-phase4-evidence-ocr-v2/prd.md` | Phase 4 任务目标；Requirements 和 Acceptance Criteria 仍为 TBD（:1-18）。 |
| `app/pipeline/ocr.py` | legacy 页渲染、原生文本分流、VLM OCR、缓存、并发与风险检测。 |
| `app/llm/client.py` | oMLX/OpenAI-compatible 调用、重试、模型选择与 LOC token 清理。 |
| `app/router/pipeline.py` | legacy 请求内 OCR -> Markdown bundle -> review 编排和 SSE 进度。 |
| `app/config.py` | 当前 oMLX URL、PaddleOCR-VL-1.6、180 DPI、8 路上限和高风险复核开关（:19-30）。 |
| `app/pipeline/classifier.py` | 基于文件名和总文字量的 legacy 文档分类（:31-42, :65-100, :103-179）。 |
| `app/pipeline/bundler.py` | 将页缓存重建为 Markdown chunk，只保留文件名/页码/文本（:85-104, :195-233）。 |
| `app/router/subjects.py` | 上传路径安全、重名改名、上传写入和全量清缓存（:93-121, :281-304, :307-383）。 |
| `app/protocols/ingestion.py` | Phase 3 已有内容哈希、魔数检测、内容寻址副本和原子替换模式（:56-68, :81-102, :105-143）。 |
| `app/protocols/docx_structure.py` | Phase 3 DOCX OOXML 结构提取：段落、嵌套表格、页眉页脚、编号、修订与稳定 `source_ref`（:1-19, :128-158, :176-204）。 |
| `app/protocols/rendering.py` | 受控 LibreOffice DOCX -> PDF、渲染参数/版本/哈希和逐页文本（:1-10, :106-139, :189-232, :275-296）。 |
| `app/protocols/source_alignment.py` | 可回验的规范化文本对齐、唯一命中、重复消歧和显式降级模式（:1-12, :52-105, :164-233）。 |
| `app/domain/contracts/evidence.py` | V2 `EvidenceSpan`/`SourceDocumentVersion`/`EvidenceSnapshot` 契约与精度互斥校验（:21-93）。 |
| `app/storage/models.py` / `app/storage/repositories.py` | V2 追加写证据表及契约仓储配置（models.py:781-835；repositories.py:842-904）。 |
| `app/workflow/*` and `.trellis/spec/backend/persistent-jobs.md` | Phase 2 持久 Job/步骤/租约/恢复底座；当前没有 OCR V2 执行器。 |
| `tests/test_phase_workflow.py` | legacy 8 路 mock 并发、高风险触发和重复幻觉去重测试（:1700-1776, :2903-2912）。 |
| `tests/v2/test_contract_logic.py` | 四级 EvidenceSpan 合同和降级约束测试（:1931-1989）；不是真实定位算法测试。 |

### 当前真实能力

| 能力 | 已有 | 实际边界/缺口 |
|---|---|---|
| 8 路 OCR | `global_vlm_semaphore()` 按 event loop 缓存 `asyncio.Semaphore(OCR_MAX_CONCURRENT)`，文件和页并发共用（`app/pipeline/ocr.py:74-88, :536-598`）。 | 仅限制 VLM 区段；全文档所有页一次性建 task，页渲染在获取 VLM semaphore 之前执行（:290-297, :451-459），因此 CPU/内存/渲染不受 8 路保护。多进程/多 worker 会各自拥有上限。 |
| 并发测试 | 9 个 mock 图片可达到峰值 8；两个同 event loop 批次合计仍为 8（`tests/test_phase_workflow.py:1700-1769`）。 | 没有真实 oMLX 负载测试、跨进程测试、大 PDF 渲染背压、取消或持久恢复测试。 |
| oMLX 交通 | `AsyncOpenAI(base_url=<OMLX>/v1)`，120s 超时，连接/超时/限流最多 3 次（`app/llm/client.py:62-71, :247-261`）。 | `call_vision_ocr()` 无条件使用 `_get_omlx_client()`，与其 docstring/可选 MiniMax 配置不一致（:414-448）。本轮对 `127.0.0.1:8000/v1/models` 的 3s 只读探测超时，不能声称当前可用。 |
| 模型选择 | 按总页数选 LONG/SHORT（`app/llm/client.py:403-426`）。 | 当前 LONG/SHORT 均为同一 `PaddleOCR-VL-1.6`（`app/config.py:23-29`）；`_choose_backend()` 已标注 deprecated，返回值在 `ocr_document()` 中计算后未使用（`app/pipeline/ocr.py:373-396, :429-432`）。 |
| 缓存 | 每文档 stem 一个目录，每页 `pN.md`/`pN.jpg`（`app/pipeline/ocr.py:94-101, :236-245`）。 | PDF 主路径只看缓存文件存在/大小，甚至不看 mtime；图片/DOCX/TXT 仅看 mtime（:482-525）。同 stem 的不同扩展名可碰撞，同字节异名不去重，模型/参数变更不失效，写入非原子。 |
| 页图 | PDF 可以 180 DPI 渲染，最大边 4000px，JPEG quality=92（`app/pipeline/ocr.py:191-211`）。 | 仅在 VLM 页/高风险复核页写 `pN.jpg`；普通原生页不产生页图。无原子写、无内容哈希、无旋转/页尺寸/坐标系 manifest，无独立 API。 |
| 原生 PDF 文本 | 打开 PDF 一次后逐页 `get_text()`，每页 >=80 字符则跳过主 OCR（`app/pipeline/ocr.py:118-125, :436-456`）。 | 字数阈值不能保证文本完整/顺序/可读；没有 word list、bbox、字符到 box 映射或坐标系。 |
| oMLX 布局 | 无已验收能力。 | `call_vision_ocr()` 对响应用正则删除所有 `<|LOC_n|>`，再合并空行（`app/llm/client.py:448-453`）；原始响应不落盘，无 layout schema/parser/contract test。 |
| 风险复核 | 否定/肯定词 + 临床触发词/时间窗会强制图像 OCR 复核（`app/pipeline/ocr.py:51-71, :252-283`）；重复行/句段和超长页会标记（:141-185）。 | 只有触发词测试与幻觉去重测试。不计算 native-vs-VLM 差异，不结构化验证小数/单位/日期，不产生可确认校对记录。 |
| 原 OCR 保留 | 高风险原生页会在同一 Markdown 中并列 native 文本和 VLM 复核文本（`app/pipeline/ocr.py:264-283`）。 | VLM 原响应在 LOC 删除、空行折叠、重复去除/超长截断后才写缓存（`app/llm/client.py:448-453`; `app/pipeline/ocr.py:141-185, :310-314`）；不是不可变原 OCR。 |
| DOCX/DOC | `python-docx` 提取非空段落后写为 `p1.md`（`app/pipeline/ocr.py:492-514`）。 | 遗漏表格、页眉页脚、文本框/图片等；所有内容被伪作第 1 页。`.doc` 也进入 `python-docx` 路径，通常不可解析。Phase 3 DOCX 结构/渲染管线更完整，但是 protocol-specific，不能直接当受试者证据服务。 |
| 失败语义 | 单文件错误记入 stats，其他文件继续（`app/pipeline/ocr.py:558-607`）。 | 单 PDF 失败页会被过滤，只要仍有任何页/旧缓存就可进入 bundle/review（:461-473; `app/router/pipeline.py:297-346`）；无页完整性契约或 stale 传播。 |
| 上传去重 | 批量测试工具会用 SHA-256 排除重复文件（`app/batch_sources.py:166-209`）。 | 正式 subject upload 仅对重名文件加 `_2` 等后缀，不计算哈希（`app/router/subjects.py:109-121, :337-348`）；批量工具的临时去重状态不是 V2 文档版本真相。 |

### 可封装复用

1. **oMLX 交通层的基本形状**：异步 OpenAI-compatible client、有界超时和短重试可作为 `OcrProvider` 适配器起点。新返回值必须是结构化 `RawOcrResponse + ParsedOcrPage + ProviderMetadata`，不能继续返回 `str`。
2. **全局准入的需求与 mock 测试样式**：保留“同一本地服务最多 8 个活跃 OCR 调用”的不变量，但准入应归属单一 OCR executor/provider pool，由持久 Job 调度；不应继续依赖模块全局 event-loop 字典。
3. **PDF 页渲染核心**：PyMuPDF 页渲染可封装为确定性 `PageRenderer`；需增加输入/输出哈希、页尺寸、rotation、DPI、图像编码版本和原子写。
4. **原生 PDF 优先路由**：文本充足页避免 VLM 的策略可保留，但决策应使用页级可读性/文本完整性信号，并同时产生 words/boxes，而不是单一 80 字符阈值。
5. **纯检测函数**：`text_requires_high_precision_review()` 和幻觉检测的临床风险知识可转成不改文本的 `OcrRiskFlag[]`；去重/截断不能作为原文变换。
6. **Phase 3 的内容寻址工件模式**：`compute_sha256()`、格式魔数检测、临时文件 + `os.replace`、复制后哈希复验是 Phase 4 上传/页图/OCR 大对象的直接参考（`app/protocols/ingestion.py:56-68, :105-143`）。
7. **Phase 3 的对齐原则**：规范化文本 + 原始索引映射、全部命中枚举、唯一性校验、有界消歧和显式降级可重用为通用 locator 内核。但 `ProtocolSourceSpan`/`StructureBlock` 类型及 protocol 表格特化恢复规则不直接进 EvidenceSpan 核心。
8. **Phase 3 DOCX 双通道方法**：OOXML 结构块用于内容完整性，受控 LibreOffice -> PDF 用于页面语义，适合作为 DOCX 证据处理的设计参考。需抽出 generic document artifact 边界，不得让 Phase 4 依赖 protocol domain 实体。

### 绝不能进入 V2 核心

1. `projects/<subject>/raw|cache|llm` 文件夹状态、Markdown bundle/chunk ID 及通过扫描文件推断业务状态。
2. 以 stem + page 或 mtime 作为缓存身份；以“缓存文件存在”作为成功证据。后端规范已明确禁止 mtime/缓存文件成为事实源（`.trellis/spec/backend/quality-guidelines.md:9-17`; `database-guidelines.md:46-51`）。
3. `call_vision_ocr() -> str` 和对 LOC/layout token 的丢弃。V2 必须先保存 provider 原始响应，再由版本化 parser 产生文本/布局派生物。
4. 将去重、截断、合并空行后的文本当作“原 OCR”；将校对文本覆盖原文。设计要求原文件和原 OCR 不变（`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md:114-125`）。
5. 原生文本与 VLM 复核直接拼成一段 Markdown，以用户自行视读代替结构化 diff/确认状态/重算范围。
6. 基于文件名的文档类别、基于页字数的 native/scan 判定作为最终业务真相。它们只能产生待确认候选或运行路由提示。
7. 请求/SSE 持有 OCR -> bundle -> review 的任务生命周期，以及 `asyncio.Lock` 作为唯一处理锁。V2 规范要求先落库 Job、租约、检查点与恢复（`.trellis/spec/backend/persistent-jobs.md:3-23`）。
8. 失败页被过滤后返回部分成功，但没有页数期望、缺页状态、stale 影响或可重试范围。
9. 短文本时自动将临床页图发往百度 OCR 的隐式外部 fallback（`app/pipeline/ocr.py:299-308`; `app/llm/client.py:513-568`）。V2 本地单机核心不能在无明确配置、数据出境说明和审计的情况下调用外部 OCR。
10. DOCX 只抽段落后写成“第 1 页”，以及将 legacy `.doc` 交给 `python-docx`。这会伪造页面语义且遗漏表格/嵌入图像。
11. 直接把 Phase 3 protocol-specific `ProtocolSourceArtifact`/`ProtocolSourceSpan` 当作受试者证据类型。可抽通用机制，不能交叉领域所有权。

### 内容哈希 OCR 缓存：最小可验证 spike

#### 目标

只证明“相同字节 + 相同页 + 相同提取器/模型/参数 = 幂等命中；任一决定性输入变化 = 失效”，不同时实现上传 UI、完整 OCR Job 或临床评测。

#### 最小指纹

```text
source_sha256
+ page_number
+ extraction_kind          # native_pdf_text | rendered_pdf_text | vision_ocr
+ provider                 # pymupdf | omlx
+ model_id
+ model_revision           # 服务无法给出时必须显式 unknown，不得省略
+ prompt_sha256
+ parser_version
+ render_params_sha256     # DPI, max dimension, rotation, image format/quality
+ request_params_sha256    # temperature, max_tokens, provider-specific options
```

对上述规范 JSON 做 SHA-256 得 `ocr_cache_key`。原文件字节使用 `SourceDocumentVersion.sha256`；不允许从文件名或 mtime 派生身份。

#### 最小工件形状

```text
data_v2/blobs/ocr_pages/<ocr_cache_key>/
  manifest.json       # 完整指纹、状态、输出哈希、页尺寸/坐标系
  raw_response.json   # provider 原始响应，不修改
  extracted_text.txt # 版本化 parser 的派生文本
  page_image.jpg      # 该路径需页图时存在
```

先写同目录临时文件，计算每个输出哈希，最后原子发布 manifest；只有 manifest 完整且所有哈希复验通过才算命中。失败/取消不写 success manifest。数据库记录工件身份、页状态和 JobStep；文件系统仅放大对象，符合 `app/storage/config.py:8-15` 和 `.trellis/spec/backend/database-guidelines.md:3-13`。

#### 最小测试矩阵

| Case | 期望 |
|---|---|
| 同字节、异文件名、同页/模型/参数 | 只调用 provider 1 次，第二次命中同一工件。 |
| 同文件名、字节改变 | 新 `source_sha256`，必定 miss。 |
| 同字节，修改 model ID/revision | 必定 miss。 |
| 同字节，修改 prompt/parser/DPI/图像质量任一项 | 必定 miss。 |
| 缓存内容被截断或 manifest/output hash 不符 | 拒绝命中，在新 JobStep 中重生成；不把损坏记录当成成功。 |
| 两个并发请求同一 key | 单航班/租约下最多一次 provider 调用；两者最终引用同一完整工件。 |
| provider 超时/部分输出/取消 | 无 success cache，页状态为可重试失败或取消，不生 EvidenceSpan。 |
| 9 个 VLM 页，两个并发批次 | 单 executor 实测活跃 provider 调用 `<=8`；渲染队列也有独立有界背压。 |

### EvidenceSpan 精度：最小可验证 spike

#### 目标与样本

使用完全合成、无 PHI 的小型 gold set，不读取/改写 legacy 临床资料：

- 4 页原生 PDF：唯一句、重复句、跨行文本、表格内的否定词/小数/单位/日期。
- 4 页扫描 PDF/图片：清晰印刷、倾斜/低分辨率、重复文字、无可用布局输出。
- 1 份 4 页 DOCX：段落、表格、页眉页脚和嵌入图像；经受控 LibreOffice 渲染后定位，页码明确标为“本次渲染页”。

每个 gold 条目固定 `source_sha256`、期望页、期望原文、是否允许精确匹配、期望最高精度；重复文本条目必须预期降级，防止“有一个命中就伪造精确”。

#### 三条定位路径

1. **Native PDF word-box path**
   - 用 PyMuPDF 的 words 输出生成稳定阅读序列、词级 box 和字符 -> word 映射。
   - 保存页宽/高、rotation、原始坐标系和 parser version；界面坐标只由页尺寸确定换算。
   - 摘录只有在规范化后唯一命中且可回验到原字符范围时才升级。所有命中词的 box 合并为 bbox；否则降级为 `text_range/page_excerpt/page_only`。
2. **oMLX layout path**
   - 新增只用于 spike 的 raw adapter：不删 LOC token，完整保存 response body 和 model ID/revision/request params。
   - 在合成页上检查是否能稳定返回文本块、坐标对、顺序和页尺寸。只有经 schema 解析、坐标边界校验和原图叠加人工核对后才声称 bbox。
   - 若 raw 响应仍只有 plain text，明确结论为“oMLX 路径最高 `text_range/page_excerpt`”，不从 LOC 序号猜坐标。
3. **Text anchor path**
   - 抽取 `app/protocols/source_alignment.py:52-105` 的规范化 + 原始索引映射思想，但以 OCRPage 的不可变 `extracted_text` 为唯一 offset 基准。
   - 唯一命中且 excerpt round-trip 一致 -> `text_range`；多命中或标准化损失不可回验 -> `page_excerpt`；连可靠摘录也无法绑定 -> `page_only` + 必填 `degradation_reason`。

#### 契约前置缺口

当前 `EvidenceSpan` 契约能表达四级精度，但不足以独立复现定位：

- `bbox` 没有坐标系、页宽/高、rotation 或对应页图工件 ID（`app/domain/contracts/evidence.py:21-46`）。
- `text_start/text_end` 没有声明是哪个不可变 OCRPage/原生文本工件的 offset；仅有 `source_document_version_id + page_number` 不能区分 parser/model revision。
- `SourceDocumentVersion` 含 sha256，但当前合同没有 source blob/storage reference（`app/domain/contracts/evidence.py:68-76`）；Phase 4 需要明确原文件大对象的定位所有权。
- 当前数据库已可在 `payload_json` 中存完整合同，但还没有 OCRPage/PageImage/CorrectionRecord 表或缓存工件契约（`app/storage/migrations/versions/0002_domain_schema.py:198-210, :230-254`）。

因此 spike 实施前应先固定最小 locator artifact identity，至少包括 `ocr_page_artifact_id/page_image_artifact_id/coordinate_space/page_width/page_height/rotation`。这是合同设计门槛，不应用额外 JSON 偷渡。

#### 最小通过标准

| 指标 | 通过条件 |
|---|---|
| 文档/页身份 | 每个 span 都回到固定 `SourceDocumentVersion.sha256` + 页工件身份；无 stem/mtime 依赖。 |
| 页码 | gold 页 100% 一致；DOCX 明确是受控渲染页，不冒充原作者分页。 |
| `text_range` | 100% 可从绑定的不可变页文本切片并回验 excerpt/anchor hash；重复文本未消歧时零虚假升级。 |
| `bbox` | 只在 schema + 坐标边界校验通过且叠加回原页的人工 gold 核对通过时产生；越界/负值/无页尺寸坐标 100% 拒绝。 |
| 降级诚实性 | 不可唯一定位的 gold 条目 100% 降级；`page_only` 100% 有具体 `degradation_reason`。 |
| oMLX 布局能力 | 用保留的 raw response 和已版本化 parser 得出明确“可/不可”结论；不将 plain text 成功当布局成功。 |
| 回归 | 现有四级契约反例仍通过，并新增损坏坐标、重复锚点、工件换绑、model/parser 变更和缺页反例。 |

### 建议的 Phase 4 最小分层

```text
api/v2 -> evidence upload service -> SourceDocumentVersion + EvidenceSnapshot
                               -> durable OCR Job/steps
workflow -> page inventory -> render/native extraction -> OCR adapter -> QC -> locator
agents   -> OcrProvider interface (oMLX implementation; raw response preserved)
domain   -> cache fingerprint / OCRPage / PageImage / CorrectionRecord / EvidenceSpan rules
storage  -> immutable blob manifests + append-only repositories
```

OCR 完成、页面完整、风险校对、EvidenceSpan 产生是不同 JobStep；任一步失败都不得伪装成“有部分文本所以完成”。这与已有持久任务规范的依赖、检查点、租约和局部重试边界一致（`.trellis/spec/backend/persistent-jobs.md:12-23, :32-42`）。

### External References

- 本轮未做新的外部网络调研；查询是当前仓库能力盘点，结论以代码、测试和已批准设计为准。
- 当前锁定版本：`pdfplumber==0.11.10`、`python-docx==1.2.0`、`openai==2.37.0`、`pymupdf==1.26.4`（`pyproject.toml:6-25`）。
- 仓库既有调研记录了 PaddleOCR-VL 1.6 算法/管线/Apple Silicon 官方文档链接（`docs/PROJECT_CONTEXT.md:1448-1469`）；本轮未重新验证其页面或将官方 pipeline 性能外推到当前 OpenAI-compatible prompt 调用。

### Related Specs

- `.trellis/spec/backend/index.md:3-29`：legacy `app/router`/`app/pipeline` 是回归锚点，V2 不应在其中继续扩张。
- `.trellis/spec/backend/directory-structure.md:3-36`：V2 依赖方向与 `legacy` 只读适配边界。
- `.trellis/spec/backend/database-guidelines.md:3-13, :31-51`：原文件/原 OCR 不可覆盖，大对象与业务状态分离，禁止 mtime 作版本。
- `.trellis/spec/backend/persistent-jobs.md:3-42`：OCR 必须成为可恢复持久步骤，不由 SSE/请求持有生命周期。
- `.trellis/spec/backend/error-handling.md:5-30, :54-60`：单文件失败需保留可重试范围，不得返回空成功。
- `.trellis/spec/backend/quality-guidelines.md:5-38`：EvidenceSpan 必须可追溯、降级明确，Agent 不产生最终业务真相。
- `.trellis/spec/guides/code-reuse-thinking-guide.md`：复用契约/机制，不复制 legacy 偶然形状。
- `.trellis/spec/guides/cross-layer-thinking-guide.md:105-122`：先固定上传 -> 工件 -> OCR -> locator -> API 边界契约和往返不变量。

## Caveats / Not Found

1. 指定的 active task 目录在当前工作树原本没有 `prd.md/design.md/implement.md`；同名 Phase 4 worktree 中的 `prd.md` 仅有目标，Requirements/Acceptance Criteria 仍是 TBD。因此本文以已批准总体设计和 Phase 4 计划为需求来源，不代替后续 PRD/design 冻结。
2. 本轮是严格只读研究，没有运行会生成缓存/临时文件的 pytest，也没有运行临床原始资料 OCR。“8 路已有测试”指对现有测试源码的核对，不是本轮新鲜复跑证据。
3. 本轮未读取任何原始临床文件或现有 OCR 页内容；页图/定位能力结论来自代码路径和契约，不是临床 gold-set 准确率结论。
4. 当前本机 oMLX model-list 只读探测在 3 秒内超时；这只能说明本轮未证实实时可用，不能区分服务未启动、模型忙或端点响应慢。
5. 未找到 OCRPage、PageImage、CorrectionRecord、内容哈希 OCR cache manifest、oMLX layout parser 或真实 EvidenceSpan locator 生成器的 V2 实现/测试。当前只有契约和合成展示数据。
6. `SourceDocumentVersion` 已有哈希与快照关系，但尚无受试者证据原文件 blob 契约；在此边界冻结前，不应开始真实上传/OCR 实施。
