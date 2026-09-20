# Execution Output: enrollment-batch-read-hardening-20260908 - worker_01

## Boundary And Context Check

- 已读初始 read set 两个文件（execution context、execution plan）。随后按 source-of-truth 清单读取 6 个授权文件：`app/llm/page_review_batch_experiment.py`、`app/llm/page_review_harness.py`、`app/llm/independent_vlm.py`、`app/domain/contracts/page_review.py`、`tests/test_page_review_batch_experiment.py`、`tests/v2/llm/test_page_review_harness.py`。附加读取（均在 app/tests 内、为确认版本号变更安全）：`rg` 全库检索 `read_page_batch|BATCH_PROMPT_VERSION` 引用（结果：除本模块与本测试外无任何引用）；`app/config.py` 中 `PAGE_REVIEW_MAX_TOKENS`（默认 12000）与两个 fallback base URL 默认值（空串）。
- 未读病例、`.env`、artifacts、个人 harness 配置；无网络、无递归委派、无会议。仅写入两个授权文件。两文件在 git 中均为未跟踪新文件（`??`），本 pass 未提交（未获授权）。
- 编辑机制说明：本运行时无独立 `apply_patch` 工具，使用 ZCode 的 Edit 工具做精确匹配的外科式替换，效果等同 apply_patch，未触碰无关改动。

## Work Performed

只改了 `app/llm/page_review_batch_experiment.py` 与 `tests/test_page_review_batch_experiment.py`，未改默认 harness，未接入任何默认流程：

1. **额度（batch experiment 1-2 处）**：初始批额度由 `route.max_tokens × 页数` 改为 `route.max_tokens` 本身（不乘页数；真实实验可直接把 `PAGE_REVIEW_MAX_TOKENS` 配为 65536，无硬编码上限）。截断时只翻倍一次（重写为显式 `while` 循环，第二次 `length` 直接以 `failure_kind="length"` 抛错），不改采样参数。
2. **调用前预检（新增 `_verify_batch_pages`）**：在构建消息与任何模型调用之前，逐页验证 (a) 页身份：`page_number` 与 `page.page_ordinal` 一致；(b) 冻结图像哈希：经 `page_to_data_url` 解码后的实际字节 sha256 必须等于 `page_image_sha256`，失败即以带 page_artifact_id 的 `ValueError` 抛出。原有 build 阶段逐页哈希校验保留，形成双重防线。
3. **429 处理（按现有 read_page 方式，不换模型）**：新增 `sleep`（默认 `asyncio.sleep`）与 `max_rate_limit_waits=12` 关键字参数；429 时等待 60 秒重试，route/model/budget 均不变，等待不消耗额度翻倍次数；复用 harness 的 `_failure_kind` 保证分类与 `read_page` 完全一致；**不查询也不使用 `fallback_base_url`**，其余传输失败显式抛 `PageReviewHarnessError`（content_filter / length / schema 分类不变）。
4. **版本号**：`BATCH_PROMPT_VERSION` 由 `page-review-batch/v1` 升为 `v2`（行为已变更）。临床提示、ClausePack、逐页 output_schema、`build_page_review_messages` 复用与 default-off 边界全部未动。
5. **合成测试**：额度断言改为 `[12000, 24000]`（两页场景，直接证伪“乘页数”）；新增 65536 直通测试 `[65536, 131072]`；新增预检两条（`image_path` 冻结后被改写 → 抛“冻结原件不一致”且零调用；`object.__setattr__` 绕过冻结构造器制造页身份漂移 → 抛“页码与图像页序不一致”且零调用）；新增 429 重试成功（`waits==[60]`，两次调用 base_url/model/budget 完全一致）、429 耗尽（`max_rate_limit_waits=2` 时共 3 次调用后 `failure_kind=="rate_limit"`）、端点失败不换模型不换端点（仅 1 次调用，`failure_kind=="endpoint"`）。缺页（`missing_page`）与混页（跨审核节点拒绝）测试原已存在，保持不动。

## Artifacts And Evidence

- `app/llm/page_review_batch_experiment.py`：额度基数、`_verify_batch_pages` 预检、429 等待循环、`BATCH_PROMPT_VERSION="page-review-batch/v2"`、模块 docstring scope 同步更新。
- `tests/test_page_review_batch_experiment.py`：2 个预算测试断言更新 + 1 个 65536 测试 + 5 个新测试（预检×2、429×2、端点不切换×1）。
- 决定性证据：`ENROLLMENT_ENV_FILE=tests/fixtures/isolated.env .venv/bin/python -m pytest -q tests/test_page_review_batch_experiment.py` → **16 passed in 0.39s**（原 10 项 + 新增 6 项）。全库 grep 证实无其他模块引用本实验模块，版本号提升不影响其他表面。

## Commands And Observations

- `rg -n "page_review_batch_experiment|read_page_batch|BATCH_PROMPT_VERSION" app tests`（排除本模块/本测试）→ 无输出，确认改版本号安全。
- `rg -n "PAGE_REVIEW_MAX_TOKENS|..._FALLBACK_BASE_URL" app/config.py` → 默认 12000 / fallback 默认空串，确认测试路由构造不依赖外部 env 中的 fallback。
- `git status --porcelain`（限定两文件）→ 均为 `??` 未跟踪，未做提交。
- pytest 命令为 context 指定的唯一验证命令，已原样执行并通过；harness 自身测试套件未运行（未获授权，且本 pass 未改 harness、无外部引用方）。

## Blockers Or Missing Environment

无阻塞。三条供 Codex 裁量的假设：

1. **私有导入**：429 分类复用了 `page_review_harness._failure_kind`（私有符号，跨同包模块导入）。因本 pass 不得改 harness，无法将其转为公开导出；如 Codex 不接受私有导入，替代方案是本地最小 `status_code==429` 判断，但会与 read_page 分类存在漂移风险。
2. **“page 身份”的解释**：实现为 `page_number == page.page_ordinal` 一致性（加上已有的 page_artifact_id 去重与同审核节点约束）。**未**额外要求同批页面共享 `source_document_version_id`——一个审核节点可跨多份文件版本，逐页记录各自携带其来源标识，加此限制会过度收紧。
3. **“allowing 65536”的解释**：按“配置直通、真实实验可配 65536”处理，未硬编码任何数值，已用专门测试覆盖 `[65536, 131072]`。预检测试用 `object.__setattr__` 模拟注册后身份漂移，因冻结 dataclass 构造器本身会先行拒绝不一致输入。

## Rerun Requests Or Next Step

无需重跑。真实模型行为、总体临床接受度不在本 pass 范围（未验证，也未声称）；两条路径（rate_limit 等待上限语义、预检错误信息文案）如 Codex 有不同裁量，均为局部一行级调整。等待 Codex 验收。
