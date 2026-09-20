已收集所有证据并进行了两次独立测量。我已拥有报告所需的一切内容 —— 正在撰写最终的会议产出。

# 会议参与者产出：enrollment-context-benchmark-review-20260908 - general_single_object

## 边界检查

- 本角色为只读设计审阅。未调用任何被测模型，未读取 `.env`、OMP/Hermes 配置、原始病例或生产数据库；未修改任何文件。
- 实际读取范围：初始读取集两份文档；任务指定的四个代码区域（`app/llm/page_review_harness.py`、`app/projections/page_review_prompt_pack.py`、领域合同 `app/domain/contracts/{page_review,page_review_context,page_review_focus,clause_pack,rules,common}.py`、`scripts/run_frozen_product_reader.py`）；为核实失败归因与执行链补充读取了 `app/services/{page_review_job_executor,page_review_execution,page_request_receipt,targeted_page_review_executor}.py`、`app/projections/clause_pack.py`、`app/projections/page_review_model_input.py`、`scripts/{audit_page_schema_failures,replay_frozen_reader_failures}.py` 及相关测试。
- 超出初始读取集的一份文档：`.trellis/tasks/09-05-phase55-dual-vlm-page-review/MODEL_COMPARISON_20260907.md`。理由：冻结脚本 `scripts/run_frozen_product_reader.py:68-69` 将其作为 test-plan 复制进每个冻结产物，且该文档记录了本审阅必需的实测数字（条款包 117,433 字符等）。这是有依据的证据扩展，不是越界扫描；未据此接触任何病例内容。
- 本地执行了两项无病例、无模型的度量（wire output_schema 尺寸、system prompt 尺寸、单条款 fixture 包尺寸），仅为纯 Python 对象序列化测量。
- 未声称最终临床/监管/视觉/浏览器验收；Codex 保留最终验收权。

## 独立工作产物

### A. 现状：逐页上下文如何组织（观察）

每页每读道的请求由 `build_page_review_messages`（`app/llm/page_review_harness.py:331-418`）组装，共三部分：

1. **System prompt（1,511 字符，本会话实测，主读道）**：密集行为规则，逐请求重复，读道内完全相同（`page_review_harness.py:354-397`）。
2. **wire output_schema（3,727 字符，本会话实测）**：`PageReviewPayload.model_json_schema()` 去掉三个代码自有派生字段（`page_review_harness.py:344-353`），全部 `additionalProperties:false`（本会话验证）。
3. **clause_pack 投影（实测约 117,433 字符/请求，来源记录见下）**：`page_review_prompt_pack`（`app/projections/page_review_prompt_pack.py:6-18`）只在**单次请求内**对 `source_text` 去重，其余逐条款全量序列化。

用户消息部分顺序固定为 `[image_url, text]`，text JSON 内字段顺序为 `page_artifact_id, page_number, review_context, clause_pack, output_schema`（`page_review_harness.py:399-416`）。这个顺序对缓存经济学有实质影响（见 F-1）。

### B. 长规则重复输入：成因、量级与归属（审查结论）

**成因**。`ClausePackClause` 携带完整结构化求值元数据：`expression`/`exception_expression`（`AtomicPredicate` 树，含 subject/attribute/comparator/value/unit/source_term/source_clause 等，`app/domain/contracts/rules.py:183-268`）与 `evidence_requirements`（含 due_stage、布尔审计位、时间窗，`rules.py:279-297`）。这些随条款包进入**每一次**页读请求。

**量级**（来源记录，`MODEL_COMPARISON_20260907.md` 第 97 行）：单页请求条款包 117,433 字符、81 个组件；其中 expression ≈45,399 字符、evidence_requirements ≈33,924 字符、**去重后原文仅 ≈3,541 字符**。即 **≈67.5% 的 wire 重量是结构化求值元数据，≈3% 是方案原文**。同文档第 89/96 行记录的真实输入 token：37,221（Qwen3.8 low）与 36,896（MiniMax-M3 high），同一页跨模型量级一致——输入侧被条款包主导。文档已明确"字符数不当作 token 数"，以下估算均以此为界。

**重复因子**。同一受试者同一节点的 N 页 × 2 主读道 = 2N 次全量条款包重发（product-input-v1 为 24 页 → 48 次；D001 46 页 → 92 次），外加触发手写三读时的次数。且今天**提供方前缀缓存无法利用这份重复**：图像 part 在前、每页字段在条款包之前（见 A-3），读道内跨页真正稳定的前缀只有 1,511 字符的 system 消息。而 GLM low 实测出现过"大量缓存命中"（同文档第 82 行）——说明云上计费路径已存在缓存变量。

**关键审查判断**：system prompt 已明确"条款包只帮助识别相关内容，不是受试者事实来源……不计算阈值、洗脱期或跨页判断"（`page_review_harness.py:397-398`），模型被禁止求值 expression；输出合同也只要求 `clause_id + region.excerpt`（`app/domain/contracts/page_review.py:158-174`）。因此 expression/evidence_requirements 对页读是**无效载荷**（payload the model must not use），占 67.5%——这是"长规则重复输入"问题的准确表述，且它**不与**"保留所有临床条件和来源"冲突，因为临床条件几乎全部在 source_text/title 里，只占 ≈3%。

### C. Schema 失败归因现状：分类、持久化、重放与五个归因陷阱（审查结论）

**分类学**（产生点全部在 `page_review_harness.py`）：传输类由 `_failure_kind`（:474-480）分为 `rate_limit`/`content_filter`/`endpoint`；模型侧为 `invalid_json`（:315-328，含 `repair_json_quotes` 启发式修复 :286-312）、`length`（:556-563，单次翻倍重试）、以及**五个不同 raise 点全部折叠为 `schema`**——非 stop 结束（:577-581）、context 不符合合同（:595-599）、归一化输入非法（:600-606）、payload 校验失败（:615-631）、引用不存在条款（:641-642）。

**持久化分层**：
- 基准路径：`run_frozen_product_reader.py:156-164` 把 `failure_kind + contract_error + validation_errors` 写入 status.json——信息完整。
- 产品路径：`page_review_job_executor.py:163-167` 只把 `{lane, failure_kind}` 写入 checkpoint，`PageLaneFailure` 合同只有 lane+kind 两字段（`page_review.py:321-323`），**pydantic 明细在产品内丢弃**。原始请求/响应以内容寻址 artifact 保留（`page_request_receipt.py:9-32`；executor:99-138 的 attempts 链），所以产品内唯一明细来源是离线重放：`scripts/replay_frozen_reader_failures.py`（仅过滤 `failure_kind=="schema"`，:30）与 `scripts/audit_page_schema_failures.py`（覆盖 schema+invalid_json，:26）。

**五个归因陷阱（本审阅发现，按严重度排序）**：
1. **重放代码版本漂移**：两个审计脚本 import 当前 app 的 `read_page`，而冻结运行以 manifest 逐文件哈希钉住 product-code（`run_frozen_product_reader.py:84-87`）。审计脚本自身既不校验也不记录其 app 树哈希。一旦 harness 演进（例如下述任何 prompt 变体），重放结论就归因到错误代码版本。这必须在第一轮对照实验**之前**修复，否则整个对照的失败归因被代码漂移污染。
2. **configuration 错误漏入 lane failure**：`read_page` 的 review_focus 不一致等配置校验（:507-513）抛 `failure_kind="configuration"`，executor 把一切 `PageReviewHarnessError` 落为 lane failure（executor:155-167）→ 产品缺陷被记成读道失败、页面进入 failed_pending_reread，污染重读队列与按读道统计的失败率。
3. **修复解析无痕通过**：`extract_json_object` 先原样解析、失败后走 `repair_json_quotes`（:315-328），修复成功与干净解析在记录上不可区分（`response_sha256` 对修复后 dict 计算，:583-584）。跨臂比较"一次通过率"时这会系统性失真。
4. **非 stop 结束被记为 schema**：provider 端行为（finish_reason 异常）与模型合同违规混在同一桶，跨 provider 比较 schema 率时引入 provider 噪声。
5. **派生字段误报**（已有前车之鉴）：wire schema 删除派生字段、代码侧重新推导（:344-353 vs :586-614）；对原始响应直接做全量合同校验会假报缺字段。`MODEL_COMPARISON` 第 84 行记录的 cms low 重放定位即此陷阱。另外 Python `json` 对重复键静默取末值——第 106 行记录的 Qwen3.8 high"重复字段"症状用现工具不可检测，需 `object_pairs_hook`。

### D. 三臂最小可用设计（满足"保留所有临床条件和来源"）

统一约束（继承对照方案第 66-78 行）：不改 ClausePack 权威合同与 PageReviewRecord；wire 投影必须是 ClausePack 的纯函数（保持 `verify_clause_pack` 与记录身份链 `page_review_harness.py:643-662` 可重放）；每臂显式 `PAGE_REVIEW_PROMPT_VERSION`；同一冻结输入、同模型、同 effort、质量不损失为采用前提。

**臂 1：逐页短上下文（最小、建议首做）**。在 `app/projections/page_review_prompt_pack.py` 增加变体投影（如 `page_review_model_pack_v2`）：逐条款保留 `clause_id/official_code/display_code/kind/title/source_text(逐字)/determination_mode` + 资料提示（fact_type+due_stage），**删除 expression 树与 evidence_requirements 审计位/时间窗**。预期能保留全部临床条件（source_text 逐字保留），wire 从 ≈122.7K 字符（包+schema+system）降至 ≈14-17K 字符估算。建议拆成两个子臂以分离变量：v2a 仅裁剪、v2b 裁剪+机导谓词摘要提示（标记"非权威"）。这复用产品既有先例——`page_review_model_input.py:6-37` 的"删审计元数据、绝不删来源证据"原则。验收：冻结页集上逐页比较 clause_signal 召回、事实键集、冲突数、手写一致性，零回退才可采用。

**臂 2：关联页小批**。批 = 同一 `source_document_version_id` 内 2-4 连续页；单请求 N 图 + 一份条款包（即使用未裁剪包也把 2N→N 次摊薄）。响应为 `{"pages":[{page_artifact_id, ...PageReviewPayload}]}` 包装合同。实现上把 `read_page`（:491-685）拆为"带重试的请求完成"与"逐条物化记录"两段，批路径逐条物化、逐条校验：**单页坏条目不毒化整批**（解析成功条目救回，失败页回退既有单页路径重跑——executor 已有 `recovery.length_override` 扩展点 :143-151 可镜像）。批级 checkpoint 增 `batch_request_sha256 + entry_index`，页记录合同不动。批大小按实测单页输出（GLM high 单页 completion 15,440 tokens）保守定为 2 起。关键验收标准：页级失败爆炸半径不得大于基线。

**臂 3：整批对照**。3a（全文档单请求带图）在真实 24-46 页语料上**预算不可行**：单密页已实测消耗 15.4K-42.4K 输出 tokens（65,536 预算），翻倍重试曾累计 ≈90K tokens；整文档输出必然截断，测的是预算不是上下文组织，仅可作 ≤6-8 页小文档研究臂并逐 provider 记录 `output_budget_enforced`（Luna 不接受 max_output_tokens）。**建议以 3b 作为"整批对照"的可产品化形态**：逐页双读完成后，加一次**纯文本**文档级对照读（输入为按 `compact_page_review_input` 先例压缩的逐页记录 + 裁剪条款包），输出跨页关联/矛盾候选，每条必须携带 `{page_artifact_ids, excerpts}`，并只经由既有针对性复核回路落地——`PageReviewFocus.candidate_excerpts` + `targeted_page_review_executor.py:55-82` 的两轮机制已实现"候选是待查材料不是答案、必须回原件核对"（`page_review_harness.py:514-529`）。来源保持：候选不经页级对原图重读永不进入事实；对账与 coverage 保持不可变。

### E. 具体建议（含代码位置与验证方法）

| # | 建议 | 位置 | 验证 |
|---|---|---|---|
| R1 | `schema` 拆子类：`missing_clause_excerpt`/`invalid_normalization_input`/`context_contract`/`payload_contract`/`unknown_clause_id`/`non_stop_finish`；`PageLaneFailure` 增可选 `detail_code`+截断 `message` | harness:577-642，`page_review.py:321-323`，executor:164 | 逐 raise 点参数化单测；对已存失败 artifact 重放并 diff |
| R2 | checkpoint 增 `failure_message`（合同不动） | executor:163-167 | 单测 |
| R3 | `configuration` 类错误改抛 `StepFailure(retryable=False)`，不再落 lane failure | executor:155-167 | review_focus 不匹配单测 |
| R4 | `extract_json_object` 返回 `repair_used`/重复键检测（`object_pairs_hook`），进 attempts 与 status.json | harness:286-328，executor:127-137 | 单测；对已留响应离线计数（chair 执行） |
| R5 | 审计脚本钉住代码版本：报告内记录 app 树哈希或比对冻结 manifest product-code；重放过滤扩展到 invalid_json/length | audit_page_schema_failures.py:19-52，replay_frozen_reader_failures.py:30 | 人工比对报告哈希；**先于任何臂实验落地** |
| R6 | 臂 1 变体投影 `page_review_model_pack_v2(a/b)`，纯函数，`require_page_reader_routes` 式 fail-closed 配置选择，prompt_version 逐变体递增 | page_review_prompt_pack.py，harness:399-406，:52 | 冻结页集零回退验收；投影单测（哈希稳定、无 expression/审计位） |
| R7 | 稳定前缀臂（零内容变更）：user 部分改为 `[text(包+schema 在前、页字段在后), image]` | harness:399-416 | 同冻结集四联测：质量/费用/时延/缓存命中字段；逐 provider 分析 |
| R8 | 臂 2 的逐条物化拆分 + 救回 + 批级 receipt | harness:491-685 拆分，executor 扩展 | 双页合成 fixture；schema 注入测试验证逐页归因 |
| R9 | 臂 3b 文档级文本对照读 → 针对性复核回路 | 新服务，复用 targeted executor:55-82 | 候选必须携带页引用与摘录；端到端 fixture 验证闭环 |

### F. 主动异议（按影响排序）

1. **最高影响： declared 臂集缺"稳定前缀/缓存"变量**。方案把"短输入可能重复规则"列为待验证假设，但测得的 GLM low 大量缓存命中表明云上读道的"重复输入成本"有一部分是**计费缓存可回收的**；本地模型（oMLX/MTPLX）无前缀缓存、重复是真实算力。不做 R7 臂，裁剪收益在云/本地两类 provider 上会得出方向相反却被混同的结论。R7 是 5 行级改动 + prompt 版本递增，零内容损失，必须在裁剪结论出来前并行测量。
2. **对照方案措辞风险**："不直接删原文或临床条件"可能被实现者读成"不能裁剪 expression"。数据说明恰好相反：临床条件 ≈3% 在 source_text 里，67.5% 的 expression/evidence_requirements 是模型被明令禁止求值的无效载荷。裁剪不触碰临床边界——但前提是 title+source_text 逐字保留、任何摘要提示显式标记非权威。
3. **跨臂失败率可比性**：批臂改变失败爆炸半径与每页成本归属。没有 R8 的逐页救回与批/页指标分配规则，臂 2/3 的 schema 失败率与单页臂不可比。
4. **时序依赖**：R5（审计脚本版本钉住）必须先于第一臂运行，否则全部离线归因结论带代码漂移混淆。
5. **对任务目标本身的一个异议**：按字面执行的"整批对照"（整批带图单请求）在真实语料上测的是输出预算截断而非上下文组织（见 D-臂 3）。安全临时路径：3b 文本对照先行；若 chair 坚持图像整批臂，限定 ≤8 页小文档并逐 provider 声明预算强制状态。

### 有界问题（请 Codex 裁决）

- **Q1**：是否授权离线读取冻结产物中 `input.json` 的 clause_pack（纯方案规则内容，无病例数据、无模型调用，位于 artifacts/phase55-model-comparison/20260907）以计算精确的裁剪比例？本 pass 中冻结目录不在本 worktree、生产库越界，故只能给出估算（14-17K 字符）。若不授权，R6 按已记录的 117,433 字符基线推进。
- **Q2**：批臂的记录身份——我的建议是 `PageReviewRecord` 合同不动，批出处只进 checkpoint（`batch_request_sha256`+`entry_index`）。请确认。
- **Q3**：臂 1 首轮是否按 v2a（仅裁剪）/v2b（裁剪+提示摘要）拆分两个 prompt 版本？我的建议是拆分（变量分离），仅当 v2a 出现相关性召回损失时才启用 v2b。

## 证据与假设

- **本会话观察（可直接复现）**：system prompt 主读道 1,511 字符；wire output_schema 3,727 字符（全量 4,223）；单条款 fixture 包 847 字符；`additionalProperties:false` 全层生效；`extra="forbid"`（`common.py:11-13`）；`PAGE_REVIEW_MAX_TOKENS` 默认 12000、超时 900s（`app/config.py:220-225`）。
- **来源记录（标注出处，未独立复算）**：条款包 117,433 字符/81 组件/构成比；输入 37,221 与 36,896 tokens；GLM low 缓存命中；cms low 重放归因陷阱；Qwen3.8 系列失败症状；65,536 预算与截断翻倍事实——均出自 `MODEL_COMPARISON_20260907.md`（行号见正文）。
- **推断**：117K→14-17K 的字符估算基于"81 组件 ≈3.5K 原文 + 每组件标题/编号/模式开销"的构成比外推，未经真实包复算（受 Q1 约束）；token 级收益须按 provider 实测。
- **推荐**：R1-R9；**猜测（显式标注）**：短输入可能减少推理涣散、批可能引入跨页注意力稀释——均为待测假设，方案第 74 行也如此要求，不预设胜者。

## 风险、差距与验证需求

- **风险**：臂 1 若丢相关性提示会降低 clause_signal 召回（下游确定性门会把它读成"无证据"）——用 v2a/v2b 拆分与冻结集零回退验收控制；臂 2 跨页归属错误靠双读对账 + page_artifact_id 校验缓解但不可根除；R1 合同加字段需兼容性测试确认旧记录仍可验证。
- **差距（本 pass 受限）**：未能复算真实 81 组件包的精确裁剪比例（Q1）；未审计 `page_review_pending.py`/`page_review_sources.py` 下游投影的连带影响（非本目标核心，已记录为后续项）；未运行任何测试套件（只读边界；修改建议的验证步骤已逐条给出，由 chair 授权执行）。
- **验证需求**：R5 先行；R1-R4 与 R6 各自的单测；臂实验统一用冻结集 + attempts/status 全量留存；云/本地 provider 分层报告（缓存命中字段、`output_budget_enforced`、计费字段不一致时按第 96 行原则保留原始计量）。

## 建议下一步

1. chair 裁决 Q1-Q3；
2. 先落 R5（审计脚本版本钉住）与 R1-R3（归因子类）——它们是所有臂实验归因可信性的前置；
3. 并行启动臂 1-v2a 与 R7 稳定前缀臂（均为最小改动、零内容损失），在冻结页集上以"质量零回退 + 云/本地分层费用/时延"出第一份对照数据；
4. 依据首批数据决定是否启用 v2b、臂 2（R8 需先落救回机制）与臂 3b；臂 3a 仅限 ≤8 页小文档且逐 provider 声明预算强制状态。
