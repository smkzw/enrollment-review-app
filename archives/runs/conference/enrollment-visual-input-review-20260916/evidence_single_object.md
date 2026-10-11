Trellis SessionStart ✓ — 已加载上下文。现按委派任务执行只读审阅。

Trellis SessionStart ✓ — 已加载上下文。

（说明：本会话在受限于只读工具的环境下完成；Bash 被沙箱拒绝，故未执行任何命令、未读取 sqlite、未展开图片二进制。所有下列结论均基于 Read/Grep/Glob 的文本证据，凡未实测处均已标注。）

# Conference Output: enrollment-visual-input-review-20260916 - evidence_single_object

## Output

### 0. 执行边界与工具可用性（必须先声明）

- 硬边界遵守：未编辑任何文件；未写入 `runs/conference/.../evidence_single_object.md`；未发起新模型调用；未读取本 worktree 之外的临床原始资料；未重置任何业务预算。
- **工具失败如实上报**：`Bash` 被运行时拒绝（`Permission to use Bash has been denied ... non-interactive mode`）。因此本报告**没有**字符/词元统计、没有 sqlite 查询、没有测试运行、**无法直接渲染页图二进制**（Read 对无扩展名 PNG 返回 `Cannot display content of binary file`）。我未尝试绕过该限制。
- 读取集合：初始读集 2 个文件；Objective 指名 5 个源文件 + 2 个生命周期文件；为验证"横放"这一关键假设，额外读取了实验根 `artifacts/mtplx-dual-basic-20260916/` 内的 `CLINICAL_READ_QC_V16.md`、`RESULT.md`、`direct-upload-receipt.json`、`effort-comparison-v17/{low,medium,xhigh}/{input.json,models.json,*/outcome.json}`、`compare_effort.py`（会议上下文第 29 行明确允许在该实验根内按需读取原图与已保存输出）。未读取其它 acceptance/phase5 运行根。

---

### 1. 结论摘要（先给最重要的一条）

**最重要的已证实缺陷（不是模型问题，也不是思考档位问题）：产品页读输入完全没有"页方向"通道——既不改像素，也不传元数据；而且对扫描来源页，页产物按构造永远记 `rotation=0`。** 六格比较的六个单元格共用同一张栅格与同一份提示，因此该比较在结构上**无法**证伪或证实任何输入呈现因素；同理，也**不能**反过来支持"旋转就能修好"。两个方向目前都未证明。

- 【证据】`app/evidence/page_processor.py:337-344`：`native is None` 时 `page_width, page_height, rotation = float(rendered.width), float(rendered.height), 0`。扫描页/无文本层页永远 `rotation=0`，**不存在记录页方向的字段值**。
- 【证据】`app/domain/contracts/ocr.py:44-65` 早已定义 `CoordinateFrame(space, page_width, page_height, rotation, transform_version)`，但该页方向语义**没有被任何页读输入或页读记录消费**。
- 【证据】`app/llm/page_review_harness.py:467-474`：送给模型的 JSON 只有 `page_artifact_id / page_number / review_context? / clause_pack / output_schema`；系统提示（420-488 行）也没有任何方向、尺寸、坐标系描述。
- 【证据】`app/services/page_review_job_service.py:122-125`：作业载荷每页只有 4 个字段（`page_artifact_id / source_document_version_id / page_number / page_image_sha256`），没有几何信息。
- 【证据】实验页面并非"图像上传"，而是 PDF：`artifacts/mtplx-dual-basic-20260916/direct-upload-receipt.json:102-104` 明确 `"file_name": "31001-基线血常规.pdf", "media_type": "application/pdf", "byte_size": 373916`。因此本轮六格**不受** `render.py` 的 EXIF 分支影响（该分支缺陷真实存在，但属另一条来源路径，见 §3 P2）。

【推断，需一次记录即可判定】该页栅格为 `1240×1755`（`CLINICAL_READ_QC_V16.md:8`），是"竖版框"；若该页真的"横放"，则横放发生在**内容/扫描摆放**层面，而**不可能**来自 PDF 的 `/Rotate=90`——因为 fitz 渲染会交换宽高，横放应得 `1755×1240`。这条推断依赖"fitz 的 `get_pixmap` 已应用 `/Rotate`"（高置信但本会话无法执行验证）。其直接后果是：**任何基于 PDF `/Rotate` 或 EXIF 标签的方向修复，对本页都会一无所获**；方向必须从栅格内容判定。

---

### 2. 六格比较的可采信度评估（对 REVIEW.md 的独立复核）

【证据】`REVIEW.md:5-7` 自述范围正确：同页、v17 提示、既有 81 条 ClausePack、串行、`claims_complete=false`、不写事实库、不改正式默认档位。`REVIEW.md:13-18` 的回执表与 `low/0/outcome.json`（`facts=21, handwriting=3, elapsed=192.23, attempts=1`）一致，说明回执表不是转述。

【证据-保真度】`artifacts/.../effort-comparison-v17/low/models.json:1-18` 与 `compare_effort.py:35-46` 证明：输入取自**产品库中真实作业** `c2e81ffe04ea48a2aa5c846cd7c5b1b1` 的 `payload_json`，页图字节直接读 `direct-upload-runtime/artifacts/page_image/<sha>`，并经 `PageReviewInput.__post_init__` 重新哈希校验（`page_review_harness.py:106-115`）。**结论：六格比较在"模型看到的字节"这一维度是忠实的产品输入复现**，这一点值得肯定。

【证据-结构性局限】
1. 六个单元格共享同一张栅格与同一份提示 → 输入呈现是常量，不可成为被检验的因子。
2. 每格仅 1 次原子调用（`attempts=1`，`REVIEW.md:20`） → 无重复，不能做任何稳定性/排名推断；`REVIEW.md:7` 已自认。
3. `REVIEW.md:24-29` 的数值反例（HGB 151→116/139、RBC 5.36→3.36/4.3/4.36、MONO% 5.5→5.36/5.6/14.3、姓名补写、NCS→NOS、EO% 7.5 加箭头、MCH 34.9/MCHC 365）属于**跨行错位/相邻行串接**模式。该模式与"页方向被旋转"是**相容**的，但也与"密集双列表格+遮挡"相容 → 单凭输出模式不能归因。

【反例/挑战】`REVIEW.md:33` 说"此次未由独立模型复核…足以否决'已可采用'"——这是**否定性结论**，成立；但同一段落也隐含了"未做单因素对照"的空白。因此按证据排序的下一步（`REVIEW.md:41-47`）中，第 3 条（方向与坐标回映）与第 4 条（紧凑投影）**都不是**"再加一格比较"能解决的，我支持这个判断。

---

### 3. 已证实（P）与假设（H）分离清单

**已证实（可由 file:line 直接复核）**

- **P1 页方向不可表达**：扫描/无文本层页 `rotation` 恒为 0（`page_processor.py:337-344`）；`CoordinateFrame.rotation` 允许 0/90/180/270（`contracts/ocr.py:58, 63-65`）却不被页读链路消费。
- **P2 两条证据平面方向处理不一致**（真实缺陷，非本轮成因）：`app/evidence/render.py:114` 用 `source.convert("RGB")` 后另存 PNG（116 行）——**不应用也不保留** EXIF 方向；而 `app/evidence/segmentation.py:195` 用 `ImageOps.exif_transpose(opened).convert("RGB")`——**应用**方向。同一份图像来源，OCR/分段面看到的是正立图，页读面看到的是未转置图，且转成 PNG 时方向标签被丢弃。对 `image/tiff` 上传路径，这是可证实的跨平面不一致。
- **P3 模型看不到方向元数据**：`page_review_harness.py:467-474`（输入字段）与 `page_review_job_service.py:122-125`（载荷字段）都不含方向/尺寸。
- **P4 模型写的 bbox 无坐标系、无边界、当前无消费者**：`contracts/page_review.py:56-59` `PageRegion{excerpt, bbox?}`；`contracts/evidence.py:23-33` 的 `BoundingBox` 仅校验 `x1>x0 and y1>y0`，**不校验页边界、不声明坐标空间**；harness 生成 schema 时（`404-419`）剥掉了 `normalized_value/normalized_unit/normalization_key`，却**保留** `region.bbox`。全仓检索显示只有 `region.excerpt` 被下游使用（`projections/page_review_visual_locators.py:86`、`services/targeted_page_review_detail.py:88,102`、`domain/page_source_association.py:57`），**没有任何消费者读取 `region.bbox`**；视觉定位工件固定 `bbox=None`、`authenticity=DEGRADED`（`page_review_visual_locators.py:101-122`）。→ 今天换视图**不会**破坏任何坐标链（风险低），但也意味着"坐标回映"目前是**空缺而非既有能力**。
- **P5 提示里的 JSON Schema 被发送两次（可证实的重复载荷）**：`page_review_harness.py:473` 把 `output_schema` 作为正文文本写入用户消息；`app/llm/page_review_transport_options.py:38-47` 会从同一条消息里再取出同一 schema 作为服务端强约束 `response_format`（mtplx 路径同时带 `extra_body.generation_mode`）；harness 自身以"服务端是否回报 not enforced"作为契约失败（`page_review_harness.py:539-547`），即产品已把该通道视为**已强制**。
- **P6 两份 schema 并不完全等价（重要陷阱）**：`app/llm/mtplx_schema_compat.py:11-12` 递归删除 `if/then/else`。因此"signal=none ⇒ region 必须为 null"这条规则只存在于**正文的那一份**里；服务端约束那份只剩结构要求。→ 不能简单删掉正文 schema（见 §5 B1）。
- **P7 发送图像的可复验性已经很强**：`services/page_request_receipt.py:19-26` 会把消息中的 data URL 解码、与 `page_image` 工件库逐字节比对，然后把 URL 替换为 `{data_prefix, page_image_sha256}` 再落 `raw_request`。这是"来源保全"的既有正面资产；也是任何辅助视图方案**必须扩展**的接口点（`read_by_sha("page_image", digest)` 是硬约束）。
- **P8 读记录身份已包含页图哈希**：`page_review_harness.py:753-776` 的 `canonical_hash` 含 `page_image_sha256`（764 行）、`prompt_version`、`contract_version`、`clause_pack_sha256` 等；`page_review_id = "page-review:" + identity[:32]`（778 行）。→ 换输入视图必然产生**新的读记录身份**，天然满足"后来证据不得静默改写早前结果"。
- **P9 续跑闸门是版本等值比较**：`page_review_execution_versions()`（`page_review_job_service.py:42-47`）在每次执行时与载荷逐键比较，不等即 `R3_EXECUTION_VERSION_CHANGED`（`page_review_job_executor.py:47-52`，`retryable=False`）。这是可用的、诚实的发布闸门。
- **P10 两读道并不同源竞争**：`page_review.py:340`（`page_review_ids` 至少 2）与 `392-400`（不得重复引用同一读道）保证对账必须正好两条读道；`page_review_job_service.py:50-72` 串行依赖已由 `serial_lanes` 表达。→ 方向修改必须对两读道**同值**，否则对账身份与"独立双读"语义一起崩。
- **P11 实验记录的身份标签有误（中等）**：`REVIEW.md:20` 把 `5245d99c…` 称为"原件SHA"，但该值在真实载荷里是 `page_image_sha256`（`effort-comparison-v17/low/input.json` 第 1 行：`page_artifact_id=pa-42b2449c025970e791128a9d-1-031fbda15275a8384cd6f745`, `page_image_sha256=5245d99c…`, `source_document_version_id=42b2449c025970e791128a9dfdaa291980375172f87bb8d8ded9302d8924fa74`）。"原件"被用于指代**派生**的 150 DPI 栅格，后续关于 DPI/分辨率的推理会因此产生歧义。
- **P12 lifespan 诊断的缺口（对照 `REVIEW.md:44` 的下一步）**：`mtplx_owned_server.py:151-161` 只在三个事件点记账（`started` 187 行、`stop_requested` 233 行、`process_group_and_port_released` 243 行）。`MtplxShutdownIncomplete` 的两个抛出点（`120-121`、`238-241`）**不写任何终态事件**；`ready()` 的网络/解析失败被 `217-225` 的循环吞掉，最终只报"未在配置的等待时间内就绪"（216 行）；子进程异常退出时既不记录退出码/信号，也不记录最后一次 health 响应。→ `REVIEW.md:44` 要的"自有模型终态回执"目前只完成了**产品请求侧**（`page_review_job_executor.py:108-138` 已有因果链），**服务进程侧仍然缺**。

**假设（不得当作结论）**

- **H1 "该页内容相对图框被旋转 90°"**：依据是 `CLINICAL_READ_QC_V16.md:8`（"1240×1755，横放扫描"）+ P1。**未证实**——我无法显示该二进制图像，也没有读到页产物的 `page_width/page_height/rotation` 记录。
- **H2 "方向是主要误差来源"**：`CLINICAL_READ_QC_V16.md:37` 已明确"尚未做单因素对照，不能断言旋转就能修复"。我同意，并认为**任何**"旋转可修复"的表述都必须先有 A0 对照。
- **H3 xhigh 断流是 OOM**：`REVIEW.md:39` 自述"不是因果证明…不补称 OOM"。我复核后同意，并补充一个可证实的归因缺口：该轮用的 **实验自建** receipt 只存 `str(exc)`（`compare_effort.py:77-79`），而**产品路径**其实已保存 `error_type/error_causes/status_code/failure_kind/elapsed`（`page_review_job_executor.py:118-133`）。→ "缺少子进程退出码与底层异常链"一半是**采集器**造成的，不是产品能力缺失。
- **H4 档位排名**：`REVIEW.md:7, 33` 已拒绝给出。正确。6 个单次样本、且输入呈现是常量，任何排名都不可复现。
- **H5 "ClausePack 约 117K 字符是输入主负担"**：`CLINICAL_READ_QC_V16.md:39` 的断言。我**未能验证**（无 Bash 无法计数）；`REVIEW.md:5-7` 的"输入约 37365 token"是服务端回报，二者口径（字符 vs token，是否计入图像 token）未对齐。

---

### 4. 建议 A：最小、来源保全的"方向"改动

#### A0（先做，零模型调用、零源文件编辑）：把"横放"从目视描述变成可复现测量

给出**一条**页产物（`pa-42b2449c025970e791128a9d-1-031fbda15275a8384cd6f745`）的确定性核查，全部离线：

1. 读该 `PageArtifact`：`page_width / page_height / rotation / renderer_version`（`contracts/ocr.py:86-89` 起字段定义；`page_processor.py:346-372` 写入）。
2. 读 `decide_route` 结果（`page_processor.py:111-140`）：本页是 `NATIVE_PDF_TEXT` 还是 `VISION_OCR`？（若是原生路线，`native.rotation` 才是权威；若是 `VISION_OCR`，则 P1 已给出结论 `rotation=0`。）
3. 确认 fitz 是否已把 `/Rotate` 烘进栅格（一次性验证：对同页取 `page.rotation` 与 `pix.width/height` 是否交换）。**若已烘入，则任何后续步骤都不得再加 `/Rotate`，否则双重旋转。**
4. 对 `page_image/<sha>` 取四个候选朝向（0/90/180/270）的**确定性**投影统计（例如行/列墨迹投影方差、水平/垂直梯度能量比），记录**四个分数**而不仅是胜者。
5. 把结果写成一个新工件/回执（例如 `page_orientation_diagnosis`），字段：`page_artifact_id, page_image_sha256, scores{0,90,180,270}, decision ∈ {r0,r90,r180,r270,undetermined}, method, method_version, claims_complete=false`。
6. `claims_complete=false`、不写事实库、不产生临床结论。

【理由】这正是 `REVIEW.md:45` 要的"只对可逆呈现做独立变量试验，不注入答案、不针对 31001 固定裁剪"的**最小可执行形态**：不调用模型、不改产品行为、不消耗两轮业务预算。同时它一次回答 Q2/H1，避免在未判定方向前就动生产链路。

#### A1（仅当 A0 判定非 `undetermined` 才做）：辅助"正立视图" + 显式变换记录

设计要点（每条都对应 Objective 的硬要求）：

| Objective 要求 | 具体做法 |
|---|---|
| 来源保全 | 原 `page_image/<sha>` 逐字节不变；`PageArtifact.page_image_sha256` 不变；**不**修改 `RENDERER_VERSION`（`render.py:28`）。 |
| 显式来源/坐标映射 | 新增派生对象 `{source_page_image_sha256, view_page_image_sha256, rotation_quarter_turns_cw ∈ {0,1,2,3}, determination_method, determination_version, source_width, source_height, view_width, view_height}`；视图字节新存放在**独立命名空间**（不要混进 `page_image/`，否则 `page_request_receipt.py:24` 的"页请求图像必须等于已保存原图"语义会被稀释成"等于任意页栅格"）。 |
| 坐标回映 | 视图→原图（像素、左上原点、y 向下）：r=90 CW 时 `x_orig = y_view`、`y_orig = H−1−x_view`（`W'=H, H'=W`）；r=180 时 `x_orig = W−1−x_view`、`y_orig = H−1−y_view`；r=270 时 `x_orig = W−1−y_view`、`y_orig = x_view`。连续坐标请用像素中心（+0.5）避免 off-by-one。EXIF 归一化到同一词汇（1→0、3→180、6→90CW、8→270CW），使 PDF 与图像来源共用**同一**方向身份。 |
| 模型独立 | 两个读道必须传**同一**视图与同一变换值；禁止按模型/按 provider/按档位决定朝向；提示文本不得写成任何具体模型专用（这也呼应 `RESULT.md:23-28`）。 |
| 临床不自动采信 | 不改 `PageReviewPayload`/`PageFactObservation` 语义，不改对账规则，不新增任何"自动接受"路径；`has_eligibility_value` 语义不变。 |
| 续跑不混输 | 在 `page_review_execution_versions()`（`page_review_job_service.py:42-47`）新增一个键（如 `page_presentation_version`），使在飞作业以 `R3_EXECUTION_VERSION_CHANGED`（`retryable=False`）诚实停下并提示新建任务，历史结果保留。 |
| 读记录身份 | `PageReviewRecord` 新增视图字段；`page_image_sha256` **保持指向来源栅格**（`page_review.py:244`）——因为 `page_review_job_service.py:120-125`、`targeted_page_review_jobs.py:67`、`page_review_job_executor.py:97-100` 都以它做连接键。若把送入字节的哈希写进 `page_image_sha256`，这些校验会一起失效或静默改义（这是本次最容易被忽略的破坏点）。`page_review_id` 因 `harness:764` 已含 `page_image_sha256`，需把视图身份也纳入 identity，保证新旧读身份不冲突。 |
| 无法判定时诚实 | `decision=undetermined` → 送**原始视图**并在记录中标明；绝不为"统一整齐"而强行旋转。**宽表横版页是必须被支持的正例，不是错误。** |

【风险控制/回滚】该方案是纯增量：新工件命名空间 + 新记录字段 + 新版本闸门键。回滚 = 移除版本键即让在飞作业按既有语义停下；历史页产物、读记录、对账工件均可原样解码（不要把新字段做成必填，参照 `PageReconciliation` 对退役字段的处理方式 `page_review.py:348-371` 的"只为字节稳定而留字段"的既有先例，但**注意**：v4 用 `reject_third_read_fields_in_current_version`（356-363 行）对当前版本**拒收**这些字段，说明本项目倾向"当前版本不写冗余字段"，新字段应走**新版本号**而不是悄悄塞进 v6）。

#### A1-附带（可单列、极小）：把 `region.bbox` 变成"视图相对"或直接下线

`PageRegion.bbox`（`page_review.py:58`）是模型书写、无坐标系、无页界校验（`evidence.py:23-33`）、当前无消费者（P4）。一旦引入视图，该字段对**未来**的红框渲染会变成主动误导。最小处置：在输出 schema 里删除 `region.bbox`（`page_review_harness.py:404-419` 已在做字段裁剪，加一处即可），或在契约上显式声明"坐标为视图坐标，须配 `view_rotation/...` 才能回映"。**这是本次最低成本、最高收益的一致性修补**，且与是否真的旋转无关。

---

### 5. 建议 B：最小、来源保全的"紧凑输入"改动

**B0（先做，零模型调用）——把"117K 字符"变成可归因账目。**
对既有 `ClausePack`（`contracts/clause_pack.py:23-84`）与 `page_review_prompt_pack`（`projections/page_review_prompt_pack.py:7-61`）做纯函数统计，输出：各字段（`source_texts` 去重文本、`expression` AST、`exception_expression`、`evidence_requirements`、`repeat_trigger_conditions`、`control_publication` 派生项、`output_schema`、系统提示）的字符数/占比，并落成一个可复算回执。理由：`REVIEW.md:46` 与 `CLINICAL_READ_QC_V16.md:39` 都指向"条款占大部分"，但**没有一份按字段的账**；在无账目的情况下做投影就是在丢失条款内容的风险下猜。这一步同样不调用模型、不改行为。

**B1（唯一有确证收益的重复项）——当且仅当该 provider 通道确实强约束格式时，去掉正文里的整份 schema 回显。**
- 依据：P5（同一 schema 发两遍）+ harness 自带的"not enforced"失败闸门（`539-547`）。
- 但**必须保留** P6 指出的、只存在于正文那份里的规则：`signal=none ⇒ region 为 null`、以及"规范值/归一化键由系统计算，无需输出"（`page_review_harness.py:410-419, 458-459, 463-465`）。做法：正文改为**紧凑约束声明**（字段名/类型清单 + 两条条件规则 + 禁止输出 `normalized_*`），完整 JSON Schema 仅走强约束通道；对**未提供** `response_format` 的 provider（`page_review_transport_options.py:20-21` 直接返回 `{}`）保持原样。
- 收益边界：这是一次纯"结构性回显"的删除，不触碰任何临床内容；但要如实说明它只占输入的一小部分（我无法给出比例——见 §8 U1）。

**B2（不要现在做）——不要截断条款内容，也不要改成两阶段双模型。**
`REVIEW.md:46-47` 已明确禁止未经设计批准的两阶段架构；`page_review_prompt_pack.py:11-18` 已示范了**唯一可接受**的压缩范式：内容去重 + 引用重定向（`source_text` → `source-N`，原文全量保留在 `source_texts`），且 `28` 行注释明确"执行回执冻结在内部，不在模型输入里重复"。若未来要压缩表达式 AST，必须沿用同一范式（保留 `clause_id/official_code/source_text_ref/determination_mode/例外`，用可复算摘要替代机械展开），并出**覆盖清单**证明"例外、时间要求、编号、节点"零丢失。

---

### 6. 生命周期诊断（`mtplx_owned_server.py` / `page_review_job_executor.py`）邻接缺陷清单

| # | 缺陷 | 位置 | 影响 | 最小修法 |
|---|---|---|---|---|
| D1 | `MtplxShutdownIncomplete` 路径**不写终态事件** | `mtplx_owned_server.py:120-121, 238-241`；记账点仅 187/233/243 | 释放失败时无终态回执，正是 `REVIEW.md:44` 想补的那一半 | 在抛出前写 `shutdown_incomplete`（含 `pid/launch_id/returncode/last_signal`） |
| D2 | `ready()` 吞掉最后一次 health 失败原因 | `204-226`（`217-225` 捕获 `HTTPError/ValueError` 后仅 sleep） | "未在等待时间内就绪"无法归因（超时？500？探活被拒？） | 记录 `last_health_error{type,status}` 与尝试次数到 lifecycle |
| D3 | 子进程异常退出无退出码/信号 | `151-161` 仅在事件时快照 `returncode`；`190-202` 检测到已退出只抛通用错 | 与 §3 H3 的"断流不可归因"直接相关 | `ready()` 失败分支读 `process.returncode` 并落账 |
| D4 | 失败回执在可重试分支被丢弃 | `page_review_job_executor.py:118-138` 写工件；但 `170-172` 抛 `StepFailure(retryable=True)` 时 `attempts` 不进入检查点 | 重试后该次失败只能靠 `logging.info` 检索，审计断链 | 失败回执 sha 一并入检查点/作业事件 |
| D5 | 比较实验用自己的 receipt，绕过产品因果链 | `compare_effort.py:66-82`（仅 `str(exc)`） | 归因证据弱于产品既有能力 | 后续比较必须复用 `page_review_job_executor.py:103-150` 的 receipt（或等价字段） |
| D6 | 429 重试可能长时间静默等待 | `page_review_harness.py:673-676`（60s × ≤12）+ `mtplx_model_lifecycle.py:21-24` 把 429 视为"可热重试" | 单页可能停顿约 12 分钟；不是缺陷但须进入验收时限说明 | 记录 `rate_limit_waits` 到读记录/回执 |
| D7 | 宽松 JSON 解析未进入身份 | `page_review_harness.py:375-388`（`strict=False` + 引号修复）vs `753-776`（只记 `format_repair`） | 一旦发生宽松解析，摘录的"逐字"可信度未在身份中披露，而对账/关联（`page_source_association.py:57`）依赖摘录 | 把 `json_repair_used` 纳入 identity/prompt_version |
| D8（正面） | 第三读退役字段的兼容处理自洽 | `page_review.py:322-371` | 无缺陷；为 A1 新增字段提供了"新版本才写"的合规样板 | 沿用该模式 |

---

### 7. 我的反对意见、与计划的分歧、以及需要 Codex 决策的点

**O1（最重要）** Objective 的措辞是"推荐最小的**方向或紧凑输入改动**"。我反对直接把它读成"可以开始改旋转/裁提示"：在没有 A0 的一次判定之前，任何旋转都是在**未证明的病因**上做生产改动，且宽度横版页会被改坏。【建议】把本次交付定义为"方向**通道**与**判定**"的最小改动；旋转本身作为 A0 通过后的第二步，并以单页对照（同页、同模型、同档位、仅视图为唯一变量）作为唯一验收证据。

**O2** `REVIEW.md:20` 的身份标签错误（P11）应修正为四字段并列：`source_document_version_id / source_sha256 / renderer_version / page_image_sha256`。否则后续"150DPI vs 300DPI"的跨身份比较（注意 `page_processor.py:196-205` 把 `renderer_version` 纳入页产物 ID，300DPI 必然是**另一个页产物**）会被记录成"同一原件的两次读数"，污染回归锚点。

**O3** 不应再投入新的档位对照。理由：输入呈现为常量时，档位扫描在原理上无法定位本类缺陷；`REVIEW.md:29-30` 的"提高思考强度不保证纠正视觉错行"与"不能用短时间判优"已足够。把预算转向 A0+B0（零模型调用）更符合"不重置两轮业务预算"的约束。

**O4** A1 若实施，**必须**把 `page_review_job_executor.py:152-163` 的 `length_override`（`max_tokens=48000, budget_scope=combined_generation`，来自 `page_review_recovery.py:81`）与 `reusable_receipts`（`page_review_job_service.py:168`、`page_review_status.py:44` 的"耗尽"判定）视为**冻结**，本改动只新增版本键，不触碰它们。

**O5** `render.py` 的 EXIF 不一致（P2）建议**单独立项**（影响 `image/tiff` 上传路径），不要塞进本次 PDF 方向议题一起改——两件事证据强度不同，混改会让验收标准无法分开判定。

**O6** 紧凑输入不要以"缩短"为目标函数，应以"零信息损失 + 可复算覆盖证明"为目标函数。

**给 Codex 的有界问题**

- **Q1** 产品是否允许引入"派生页视图"这一新的身份维度（新工件命名空间 + 读记录新字段），还是"每页产物唯一页图"是硬约束？（决定 A1 落在传输层还是存储层。）
- **Q2** 请给出 `pa-42b2449c025970e791128a9d-1-031fbda15275a8384cd6f745` 的 `PageArtifact.{page_width,page_height,rotation,renderer_version}` 与最终 `ExtractionRoute`。**这一条记录即可判定 H1**，且只有 Owner 能读库（我无 Bash/无 sqlite）。
- **Q3** 在"不新增模型调用"的约束下，是否接受**确定性启发式 + 显式 `undetermined`** 作为方向判定方法（而非 OCR/VLM 判向）？
- **Q4** 送视图字节时，`PageReviewRecord.page_image_sha256` 是否仍指向**来源栅格**（我的建议），还是契约要求写"实送字节哈希"（若是后者，请同时给出 `page_review_job_service.py:120-125` / `targeted_page_review_jobs.py:67` / `page_review_job_executor.py:97-100` 三处连接键的替代方案）？
- **Q5** 是否同意把六格比较**结项**为"未建立档位可靠性；输入呈现未被检验"，并把下一步限定为 A0+B0？

**安全临时路径（在 Q1–Q5 未答前）**：仅执行 A0 与 B0 —— 二者都是只读/只算、不新增模型调用、不改源文件、不影响两轮预算、不产生任何临床采信，可在任何回答下安全推进。

---

### 8. 我未能验证的部分（不确定清单，不得当作已验证）

- **U1** 无 Bash → 未做任何字符/词元计数，"ClausePack 117K 字符"、"输入 37365 token"、"两份 schema 各占多少"均**未核实**；B1 的收益比例未知。
- **U2** 无法渲染二进制页图（Read 拒绝无扩展名 PNG），**未**亲眼看"HGB/RBC/MONO%/姓名"反例；这些是 Owner 目视观察（`CLINICAL_READ_QC_V16.md:19-26`、`REVIEW.md:24-31`），我只复核了其内部一致性与记账方式。
- **U3** 未读 `raw_request/*`（含完整 37K 提示）与模型输出全文，故未独立复核六格的 facts/handwriting 计数含义（仅核到 `outcome.json` 数字）。
- **U4** 未验证"fitz 的 `get_pixmap` 是否应用 `/Rotate`"，该假设是 §1 推断的前提；A0 第 3 项专门用来一次判定。
- **U5** 未运行任何测试/静态检查，未确认 A1 方案在现有测试套件（如 `tests/v2/evidence/test_page_artifacts_gold.py:535-549` 对 `renderer_version` 的黄金断言）下的兼容性——实施前需由 Owner 跑一次。

**一句话给 Codex**：六格比较作为"否定性结论"成立，但它证明的是"同页同输入下没有可用档位"，而不是"模型不行"或"旋转能修"；本页方向至今**没有任何产品字段可以表达**（P1/P3），这是当前最值得花零成本去判定的空档；而紧凑输入侧唯一**已证实**的浪费是 schema 重复（P5），且必须保住只存在于正文那份的条件规则（P6）。
