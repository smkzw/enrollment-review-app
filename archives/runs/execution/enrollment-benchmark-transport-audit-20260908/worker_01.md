所有证据已收集完毕。验证确认：直接调用方式确实失败（`ModuleNotFoundError: No module named 'app'`），而 `-m` 命名空间导入可行；生产执行器与 runner 的输入构造一致；`output_lengths` 在生产会落盘而 runner 不会。审计完成，以下是完整报告。

# Execution Output: enrollment-benchmark-transport-audit-20260908 - worker_01

## Boundary And Context Check

- 已读初始读取集：`context/enrollment-benchmark-transport-audit-20260908_execution_context.md`、`plans/codex_execution_enrollment-benchmark-transport-audit-20260908.md`。
- 未调用任何模型或远程/本地推理服务；未读取 `~/.omp/agent/agent.db`、`.env`、OMP 配置内容或任何原始病例/临床资料。`benchmark_direct_transports.py:11-21` 的 OAuth 读取仅做静态代码审阅，未执行。
- 额外只读读取了直接依赖（`app/config.py`、`app/domain/contracts/page_review.py`、`page_review_context.py`、`clause_pack.py`、`app/llm/independent_vlm.py`、`app/projections/clause_pack.py`、`page_review_prompt_pack.py`、`app/domain/publication.py`、`app/evidence/artifacts.py`、`app/storage/config.py`、`app/services/page_review_job_executor.py` 相关片段），以及横评计划 `.trellis/tasks/09-05-phase55-dual-vlm-page-review/MODEL_COMPARISON_20260907.md`（作为横评意图与裁决依据，非临床材料）。理由：任务要求审计“直接依赖”与“冻结版本和产品提示等价性”，上述文件是被审三文件的直接 import 目标和对照基准。
- 未写入任何文件；本报告通过最终响应返回，由 runner 持久化到 `runs/execution/enrollment-benchmark-transport-audit-20260908/worker_01.md`。

## Work Performed

只读审计了 `scripts/benchmark_direct_transports.py`（99 行）、`scripts/run_frozen_product_reader.py`（157 行）、`app/llm/page_review_harness.py`（705 行）及其直接依赖，按预算、模型标识、effort、时间统计、错误处理、冻结版本、产品提示等价性七个维度逐项核对，并对导入机制做了两条不触发模型调用的实证检查。以下发现按严重性排列；每条给 `文件:行号`、证据、最小修复建议。**[证据]** = 直接代码/命令证据；**[推断]** = 逻辑推论；**[未验证]** = 需真实调用才能确认。

### 高严重性（横评有效性核心）

**H1 — 输出预算在 openai-codex 通道被静默丢弃，且预算豁免标志未进入任何汇总产物**
- [证据] `benchmark_direct_transports.py:62-64`：注释明言 "Codex subscription transport does not accept max_output_tokens"，body 中无预算字段；`:98` 返回 `output_budget_enforced: provider != 'openai-codex'`。google 通道 `:47` 将 budget 写入 `generationConfig.maxOutputTokens`（Gemini 语义下 thinking tokens 计入该上限，[未验证]）。
- [证据] 横评裁决（MODEL_COMPARISON_20260907.md）要求 65536 tokens 显式预算、"厂商不支持…标明能力差异，不静默降至12K"。标志只落在 `transport-{index}.json`；`run_frozen_product_reader.py:116-117` 的 receipts 只记录 `usage/finish_reason/response_model`，`status.json`、`record.json` 均无此标志。仅看 receipts.json 会把“无预算”的 codex 用量与“有预算”的 google 用量当作同口径对比。
- 最小修复：runner 在 `receipt.update(...)`（`run_frozen_product_reader.py:116`）与 `status.json` 中带上 `output_budget_enforced`；google 侧 `maxOutputTokens` 额外拆分记录 thoughts 与正文占比（依赖 [未验证] 的服务端计量）。

**H2 — codex 截断被错误归类为 schema 失败，违反“全部保留失败、截断”裁决**
- [证据] `benchmark_direct_transports.py:89-93`：`response.incomplete` 事件只取 `response.status`（'incomplete'）作 finish_reason，丢弃 `incomplete_details`；`run_frozen_product_reader.py:106-107` 的 finish 映射表 `{'STOP','completed','MAX_TOKENS'}` 不含 'incomplete'；于是 `page_review_harness.py:577-581` 走到“非 stop → failure_kind='schema'（模型未确认资料判读完整结束）”，而产品语义应为 `length`（额度用尽）。后果：codex 截断既不能触发 `read_page` 的 max_tokens 加倍重试（`:556-562`），失败类别也是错的。
- 最小修复：transport 捕获 `response.incomplete_details`（字段名按 OpenAI responses API 约定，[未验证] 需以真实截断响应核实），runner 将 `incomplete + max_output_tokens` 映射为 `'length'`。

### 中严重性

**M1 — effort 观测性在三条通道不对称，effort 真实性仅能事后部分验证**
- [证据] codex 通道从不捕获思考：`benchmark_direct_transports.py:84-86` 只在 google 分支累加 `thought`，codex 分支无任何 reasoning summary delta 处理 → `thought_characters` 恒为 0（`:97`），与 effort 无关，是误导性字段。
- [证据] google 通道只记 `len(thought)`（`:97`），思考原文被丢弃，无法定性核查 effort。
- [证据] `page_review_harness.py:483-488` `_usage_counts` 只保留顶层数值键，codex `usage.output_tokens_details.reasoning_tokens`、zhipu `completion_tokens_details` 等嵌套推理 token 数在 `record.json` 中丢失（原始 usage 仅存于 `response-{index}.json`）。
- [证据] `page_review_harness.py:452-455` 计算的 `output_lengths.reasoning_content_characters` 在生产会落盘（`page_review_job_executor.py:135`），但 benchmark runner 的 `PageCompletion`（`run_frozen_product_reader.py:108-110`）与 `response-{index}.json`/receipts（`:113-117`）均未携带——基准路径反而丢失了产品留存的字符级证据。
- 最小修复：codex 分支处理 reasoning summary 事件或明确置 `thought_characters: null`；runner 把 `output_lengths` 写入 response/receipt；`_usage_counts` 前将嵌套 reasoning tokens 提升为顶层 `reasoning_tokens` 数值键。

**M2 — 超时不对称：产品 900s vs 基准传输硬编码 600s**
- [证据] `app/config.py:224-226` `PAGE_REVIEW_TIMEOUT_SECONDS` 默认 900；`benchmark_direct_transports.py:66` `httpx.AsyncClient(timeout=600)`。耗时 600–900s 的页面在订阅通道失败而产品路径可通过，污染跨通道时间统计与失败对比。
- 最小修复：transport 超时改为读 `PAGE_REVIEW_TIMEOUT_SECONDS`（经 `os.getenv` 或传参），缺省 900。

**M3 — 网络路径不对称：基准传输 `trust_env=True`，产品全链路 `trust_env=False`**
- [证据] `benchmark_direct_transports.py:66` vs `page_review_harness.py:241,427-428`。系统代理（HTTP(S)_PROXY）只影响基准通道，构成计划所称“必要协议适配”之外的非受控传输差异。
- 最小修复：transport 改 `trust_env=False`。

**M4 — 订阅通道 429 被当作终态 endpoint 失败，重试语义与产品路径不等价**
- [证据] `run_frozen_product_reader.py:104-105` 对 `http_status != 200` 抛 `RuntimeError("Subscription transport failed…")`，无 `status_code` 属性；`page_review_harness.py:474-480` `_failure_kind` 因此归为 "endpoint"，跳过 rate_limit 的 12×60s 等待（`:539-543`）。产品 OpenAI 兼容路径异常自带 `status_code`，429 会正常等待重试。计划要求“正式…重试…均使用被测产品环节实际配置”。
- 最小修复：抛出时附带 `status_code`（`exc.status_code = wire.get("http_status")`），让 `_failure_kind` 正确分类；错误正文已留在 transport 文件。

**M5 — benchmark 默认 effort 与产品 main-A 默认不一致，“产品等价运行”缺省参数即失真**
- [证据] 产品路由 effort 为 main-A `low`（`page_review_harness.py:190`）、main-B `high`（`:205`）；runner 无条件 `replace(route, reasoning_effort=args.effort, ...)`（`run_frozen_product_reader.py:70`）且默认 `--effort high`（`:148`）。按计划“不同 effort 独立计分”覆盖 effort 是有意设计，但以默认参数宣称“冻结产品读片器”时 main-A 实际跑的是非产品 effort。
- 最小修复：`--effort` 增加 `default=None`，None 时保留路由原 effort 并在 receipts 中记录“产品默认”；显式覆盖时打印提示。

**M6 — `--effort max` 缺少按通道的能力校验**
- [证据] CLI 允许 `max`（`run_frozen_product_reader.py:148`），合同允许（`page_review.py:249` `Literal["low","high","max"]`）；但 codex `reasoning.effort`（transport `:64`）与 google `thinkingLevel: 'MAX'`（`:47`，`effort.upper()`）是否接受 `'max'`/`'MAX'` [未验证]。若被拒，表现为横评中途 400 而非计划要求的“标明能力差异”。
- 最小修复：为两个订阅通道建立 effort→wire 值映射表并预检，不支持时在 receipts 写 `effort_unsupported` 而非发起注定失败的调用。

**M7 — 规范产物 record.json 不含实际服务模型标识（requested ≠ served 无法在产品记录内闭合）**
- [证据] `PageReviewRecord`（`page_review.py:237-260`）只有请求侧 `model/provider/endpoint_base_url`，无 `response_model/response_id`；`run_frozen_product_reader.py:674` 构造 record 时也不传。实际模型只存在于 `response-{index}.json`/receipts。计划 §3 要求“每次运行保存…实际响应模型”。
- 最小修复：benchmark 侧把 `response_model/response_id` 并入 `status.json`；产品合同是否加字段超出本次范围，交 Codex 决策。

### 低严重性

**L1 — 直接调用方式已损坏（已实证）**：`python3 scripts/run_frozen_product_reader.py --help` 在 `:13` 即 `ModuleNotFoundError: No module named 'app'`（失败先于任何 app/.env 加载）；`scripts/` 无 `__init__.py`，但 `python3 -c "from scripts.benchmark_direct_transports import subscription_completion"` 自仓库根可成功导入（命名空间包）。最小修复：脚本头部加 `sys.path` 引导（`ROOT = Path(__file__).resolve().parents[1]`）或在文档固定 `python -m scripts.run_frozen_product_reader` 调用方式。

**L2 — 错误返回结构不一致**：`benchmark_direct_transports.py:70` 与 `:94-95` 两个错误返回缺 `usage/response_model/response_id/finish_reason/thought_characters/output_budget_enforced` 键，与 `:96-98` 成功结构不同形；现调用方靠先查 `error` 规避（runner `:104`），属潜在 KeyError 陷阱。最小修复：统一返回结构、错误字段置 None。

**L3 — SSE 解析无保护**：`benchmark_direct_transports.py:74` `json.loads(line[5:])` 对非 JSON data 行会抛 `JSONDecodeError`，此时 `transport-{index}.json` 尚未保存（runner `:103` 在返回后才保存），已积累 text 丢失。最小修复：try/except 后返回带部分 text 的结构化错误。

**L4 — provider 二分派发与凭据形状无校验**：`benchmark_direct_transports.py:48` 任何非 `google-antigravity` 的 provider 都走 codex 端点；`:26/:50/:44` 直接取 `credential['access'/'accountId'/'projectId']`，键名对 agent.db 实际 schema [未验证]，不匹配时 KeyError 无上下文。最小修复：显式 provider→(endpoint, 凭据键) 注册表 + 取值前形状校验。

**L5 — finish_reason 映射不完整**：`run_frozen_product_reader.py:106-107` 缺 google `SAFETY/RECITATION` 等（应映射 content_filter，配合 `page_review_harness.py:565-575`）与 codex `incomplete/failed`；两通道 finish 值域（`STOP` vs `completed`）与 usage 键名（`usageMetadata` vs OpenAI `usage`）也未归一，跨通道对比需人工映射。

**L6 — 本地 provider 端口硬编码**：`run_frozen_product_reader.py:77` omlx 写死 `127.0.0.1:8001/v1`，而 `app/config.py:111-128` oMLX 端口发现逻辑默认 8000；无 `--base-url` 覆盖。最小修复：从 `OMLX_BASE_URL`/`MTPLX_BASE_URL` 派生并允许 CLI 覆盖。

**L7 — `--provider` 不带 `--model` 时路由身份错标**：runner 从不调用 `resolve_route_model`/`preflight`（`page_review_harness.py:238-283` 存在但未用），main-A 默认 model id 会被发往替代 provider，产生必然 404 且 receipts 记录的是虚假路由身份。最小修复：`--provider` 时强制 `--model` 或先跑 `resolve_route_model`。

**L8 — CLI 输入校验缺口**：run 模式缺 `--output` 时 `run_frozen_product_reader.py:79` 对 None 调 `.mkdir` 崩溃（`:146` 未设 required）；`--page-index`（`:151`）无界且允许负索引（`:84`）；freeze 模式漏 `--source-job` 时报误导性的 "Expected a completed source job"（`:30-32`）。

**L9 — freeze 过度复制与校验盲区**：`run_frozen_product_reader.py:34-35` 整库备份 + `:46` 整个 blobs 目录把无关作业/受试者数据带进基准目录（本机单用户可接受，建议只复制该作业引用的 blob）；`:51` 计划文档路径硬编码（本 worktree 已验证存在），缺失即崩；manifest 运行时校验（`:65-68`）只覆盖 `product-code/*`，`runner.py` 与 transport 版本变化不校验。

**L10 — 请求文件内嵌全图 base64**：`page_review_harness.py:414` 构造的 data URL 被 runner `:94-95` 原样写入 `request-{index}.json`，临床页图像按尝试次数重复落盘。计划允许结果入 `artifacts/phase55-model-comparison/`，属可接受但应知悉的数据放大。

**L11 — 两个脚本无回归测试**：`tests/` 与 `scripts/` 中 grep 无引用（仅 `__pycache__`）。建议最小冒烟测试：伪造 completion 注入跑通 runner 的 save/verify 路径。

**L12 — 配置潜在笔误（路径外发现，顺带报告）**：`app/config.py:162` `MINIMAX_BASE_URL = "https://mimimax.cn/v1"` 疑似 `minimax` 拼写错误；不在本次被审调用链上（MAIN_B 默认走 mediportal 网关），但一旦启用即是把请求发往可疑相似域名。

### 正向等价性确认（审计通过项）

- **产品提示等价**：runner 完全复用产品 harness——`read_page`、`build_page_review_messages`、`require_page_reader_routes` 未改动（`run_frozen_product_reader.py:18,69,128`）；prompt 版本常量（`page_review_harness.py:52-54`）随 record 落盘。
- **输入构造与生产逐字节一致**：`run_frozen_product_reader.py:86-89` 与 `page_review_job_executor.py:96-99` 完全相同（`PageReviewInput(**page, review_context=…, PageVisionInput(source_ref=page_artifact_id, page_ordinal=page_number, image_bytes=…))`），且 `page_review_harness.py:93-102` 的哈希/页序自检在两条路径同样生效。
- **图像保真双重校验**：发送前重编码→解码→sha256 对账冻结原件（`page_review_harness.py:336-341`）。
- **冻结完整性设计扎实**：manifest 对代码+输入+图像全量 sha256；每次运行重验所有文件并比对 `product-code` 与当前 `app`（`run_frozen_product_reader.py:53-56,62-68`）；`fallback_base_url=""` 可靠关闭端点回退（`page_review_harness.py:545-546,566`）；manifest 明示 `clinical_acceptance/gold_in_model_input` 标志。
- **密钥不落记录**：request/response/receipt/transport 文件均无凭据；OAuth 为每次调用的一次性只读 sqlite 访问；环境凭据缺失时 fail-closed（`page_review_harness.py:152-166`）。
- **时间统计**：每次 completion 用 `time.monotonic()` 计时且失败也入 receipts（`run_frozen_product_reader.py:96,119-125`），符合计划；未统计首 token 延迟与 read_page 整体（含重试等待）耗时，属已知粒度限制。

## Artifacts And Evidence

- 审阅结果即本报告（含全部 `文件:行号`）。未创建或修改任何文件（runner 管理 `runs/execution/.../worker_01.md`，我未触碰）。
- 关键证据行号索引：预算丢弃 `benchmark_direct_transports.py:62-64,98`；google 预算 `:47`；截断事件 `:89-93`；finish 映射 `run_frozen_product_reader.py:106-107`；effort 覆盖 `:70,148`；产品超时 `app/config.py:224-226`；产品 effort `page_review_harness.py:190,205`；usage 过滤 `:483-488`；output_lengths 生产留存 `page_review_job_executor.py:135`；record 合同无 response_model `page_review.py:237-260`。

## Commands And Observations

| 命令 | 观察 |
|---|---|
| `ls scripts/`、`ls .trellis/tasks/09-05-.../MODEL_COMPARISON_20260907.md` | `scripts/` 无 `__init__.py`；计划文档在本 worktree 存在 |
| `python3 scripts/run_frozen_product_reader.py --help` | `ModuleNotFoundError: No module named 'app'`（`:13` 即失败，未触及 .env/模型）——证实 L1 |
| `python3 -c "from scripts.benchmark_direct_transports import subscription_completion; ..."` | 命名空间导入成功（仅加载 json/sqlite3/pathlib/uuid/httpx，无副作用、无凭据访问）——证实 `-m` 调用可行 |
| `grep`/`sed` 读取直接依赖签名（`read_by_sha`、`resolve_data_paths`、`canonical_hash`、`verify_clause_pack`、`page_review_prompt_pack`、`PageVisionInput`、`page_to_data_url`） | 与 runner 调用方式全部匹配；生产 executor 输入构造与 runner 一致 |
| `python3 -c "import openai, httpx; print(...)"` | openai 2.38.0（pyproject 钉 2.37.0，环境漂移仅记录）、httpx 0.28.1、Python 3.14.7（脚本 `__pycache__` 为 cpython-312，末次运行环境为 3.12） |

## Blockers Or Missing Environment

- 无阻塞性缺口。以下为**未验证限制**（边界内不可验证，修复前需真实调用确认）：
  1. codex 后端对 `reasoning.effort='max'` 与 google 对 `thinkingLevel='MAX'` 的接受性；`response.incomplete_details` 实际字段名与载荷形状。
  2. Gemini `maxOutputTokens` 是否包含 thinking tokens（影响 google 侧有效正文预算解读）。
  3. codex 通道对 data-URL `input_image` 的支持。
  4. `~/.omp/agent/agent.db` 凭据 JSON 的实际键名（`access`/`accountId`/`projectId`）——按边界未读取。
  5. 订阅通道在 `read_page` 重试循环（rate_limit 等待、length 加倍）下的真实行为。

## Rerun Requests Or Next Step

无需重跑。建议 Codex 按以下顺序处置（均最小改动，且 H1/H2/M1/M4 集中在 `benchmark_direct_transports.py` + `run_frozen_product_reader.py` 两个基准专用文件，不触碰产品路径）：
1. 先修 H1+H2+M4（预算/截断/429 语义），再修 M1（effort 观测补齐）——四项决定横评数据是否同口径；
2. M2/M3（超时、trust_env）一行级修复；
3. M5/M6（effort 默认与能力预检）在发起下一批横评前落地；
4. M7 与 L 系列可批后处理；L12 转交 config 维护者确认。
[未验证] 项建议在下一次真实横评调用的 transport-N.json 中先采集证据，再实现 H2 的 `incomplete_details` 解析。
