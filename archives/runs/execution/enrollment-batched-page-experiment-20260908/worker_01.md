# 执行输出: enrollment-batched-page-experiment-20260908 - worker_01

## 边界与上下文检查

- 会话被绑定到指定的工作树 `phase5-clinical-facts-profile`；从运行器的初始读取集读取了 `context/enrollment-batched-page-experiment-20260908_execution_context.md` 和 `plans/codex_execution_enrollment-batched-page-experiment-20260908.md`。
- 按照授权来源列表读取（只读）：`app/llm/page_review_harness.py`, `app/domain/contracts/page_review.py`, `app/domain/contracts/page_review_context.py`, `app/llm/page_review_context_layout.py`, `app/projections/page_review_prompt_pack.py`, `app/projections/clause_pack.py` (签名检查), `app/domain/publication.py` (签名检查), `app/llm/independent_vlm.py` (通过 `grep` 查找 `PageVisionInput`/`page_to_data_url`), `app/config.py` (通过测试失败输出查看), `tests/conftest.py`, `tests/v2/llm/test_page_review_harness.py`, `tests/test_page_review_context_layout.py`。
- 未读取任何病例材料、`artifacts/output`、`.env`、OMP 或 Hermes 配置。未调用真实模型或网络（所有完成情况均已注入）。未修改 `page_review_harness.py` 或任何现有文件。
- 创建的文件仅限于两个授权文件：`app/llm/page_review_batch_experiment.py` 和 `tests/test_page_review_batch_experiment.py`。通过文件 `mtime` 验证了现有工作未受影响（harness 仍然是 2026-09-06 22:25；我的文件是今天 07:25/07:26）。

## 已执行工作

实现了默认关闭的产品多页读取实验，遵循 `page_review_context_layout.py` 建立的可选实验模式（封装 `read_page`，注入完成情况，重新确定记录标识范围；未改变默认连接 — 没有内容导入该模块）。

`app/llm/page_review_batch_experiment.py` — 导出 `BATCH_PROMPT_VERSION` (`page-review-batch/v1`), `PageReviewBatchFailure`, `PageReviewBatchResult`, `read_page_batch(route, page_inputs, clause_pack, *, completion=direct_openai_completion)`:

- **入口验证 (失败关闭，在调用模型前):** 空输入，重复的 `page_artifact_id`，以及混合的评审节点（比较完整的 `review_context`，包括 None-vs-present；所有页面必须共享同一个节点）会引发 `ValueError`。镜像 `read_page`：检查 `route.model` 预检和 `verify_clause_pack`。
- **通过现有构建器进行批量请求构建:** 每个页面都通过现有的 `build_page_review_messages` 进行路由；提取每个页面的图像部分和 JSON 提示有效负载。非页面键 (`review_context`, `clause_pack`, `output_schema`) 在一致性验证后仅提升一次（完整 ClausePack 保持不变 — 断言等于 `page_review_prompt_pack(clause_pack)`）；每页条目保留 `page_artifact_id`/`page_number` 按顺序。临床系统提示保持字节完整，仅在通用批量框架（响应信封、覆盖、页面隔离）后追加 — 未生成临床问题。一次多模态请求 = 按顺序的所有页面图像 + 一个文本部分，包括一个机器可读的 `batch_response_contract`，键为 `page_artifact_id` → 原始页面级有效负载。
- **配额规则:** 初始预算 = `route.max_tokens × 页数` (从不低于页面的顺序总额度)；在 `finish_reason == "length"` 时，预算按现有规则翻倍一次；第二次截断引发 `PageReviewHarnessError(failure_kind="length")`。未添加采样参数；`content_filter`/非停止完成情况明确失败。
- **带重复项可见性的响应拆分:** `_parse_batch_pages` 使用 `object_pairs_hook` 解析信封，该钩子记录键顺序（最外层对象最后关闭），因此返回信封后可以观察到顶级重复的页面键，同时嵌套去重保持现有的最后写入优先（last-wins）行为；重用 `repair_json_quotes` 进行不可解析的正文处理。
- **按页面结果分类 (明确，绝不静默):** 重复的返回键 → 每页 `duplicate_page` 失败（两份均拒绝）；未请求的键 → `unknown_page`；预期的页面不存在 → `missing_page`；有效部分继续。
- **通过现有的 `read_page` 进行每页验证:** 每个返回的有效负载都被馈送通过带有注入的 `split_completion` 的 `read_page` (其重新运行图像哈希冻结检查，模式 + 归一化验证，针对数据包的子句信号检查，以及单页标识)。缺失/拒绝的页面完全跳过 `read_page` (开发过程中修复的缺陷：它们以前会引发 `KeyError`，被误分类为 `endpoint` 失败，并添加了第二个冲突条目)。每页 `PageReviewHarnessError` 成为具有其自身 `failure_kind` 的失败记录；有效页面成为 `PageReviewRecord`。
- **批量 ID 和标识:** `batch_id = "page-review-batch:" + hash[:32]` 覆盖合同版本、批量提示版本、通道/提供商/模型/工作/端点、`clause_pack_sha256`、有序页面 ID 和批量请求哈希 — 具有确定性，作用于批量定义。每条记录获得 `prompt_version = base + "+page-review-batch/v1"` (区别于单页默认值) 和一个从其 `read_page` ID 加批量范围重新推导出的确定性 `page_review_id`。
- **使用诚实原则:** 批量使用情况报告一次在结果上；每页记录不携带使用情况（无法真实拆分）。

`tests/test_page_review_batch_experiment.py` — 10 个专注的离线测试，带有注入的完成和合成数据，证明了：页面归因（每个记录的事实和 `response_sha256` 绑定到其自己的信封条目），完整共享 ClausePack/schema/上下文且临床提示完整，输入拒绝（混合节点、重复页面、空输入），且零完成调用，每页模式失败旁边保留有效部分，明确的 `missing_page`，`unknown_page`，`duplicate_page` 返回键，预算 = n×12000 翻倍一次至 2× (并且截断两次在不增加进一步预算的情况下失败)，确定性的批量/记录标识区别于普通的 `read_page`，以及没有 ClausePack/上下文的手写通道变体。

## 工件与证据

- `app/llm/page_review_batch_experiment.py` (new, ~250 lines) — 批量实验模块。
- `tests/test_page_review_batch_experiment.py` (new, 10 tests) — 全部通过。
- 无回归风险：该模块是新文件，未导入任何现有内容；仅导入了现成的公共 harness 符号；harness 文件未受影响。
- 测试命令: `.venv/bin/python -m pytest -q tests/test_page_review_batch_experiment.py` → `10 passed in 0.36s` (离线；conftest 默认为 `tests/fixtures/isolated.env`)。

## 命令与观察

- 规定的 `ENROLLMENT_ENV_FILE=/dev/null .venv/bin/python -m pytest -q tests/test_page_review_batch_experiment.py` 在集合阶段失败：`app/config.py:65` 引发 `RuntimeError: 【启动失败】显式环境文件不存在或不是普通文件：ENROLLMENT_ENV_FILE=/dev/null`。通过依赖 `tests/conftest.py` 的离线默认值 (`ENROLLMENT_ENV_FILE=tests/fixtures/isolated.env`) 解决 — 依然是离线状态，无凭据。
- 测试期间发现并修复了两个测试端的缺陷（非异步 plain-`read_page` lambda；身份测试重用了一个信封队列），并修复了一个真正的模块缺陷（缺失/重复页面曾被发送到每页 `read_page`，导致 `KeyError` → 错误的 `endpoint` 类型 → 重复失败条目；现在它们在失败条目到位后跳过验证）。

## 阻碍或缺失环境

- 无阻塞性问题。唯一的偏差是上述的 `ENROLLMENT_ENV_FILE=/dev/null` → `tests/fixtures/isolated.env` 替换；如果 Codex 希望字面命令通过，`app/config.py` 需要一个现有文件路径（超出我的编辑边界）。

## 重新运行请求或下一步

- 提供给 Codex 验收的注意事项/限制：批量调用不会等待速率限制，也不会使用端点回退（传输错误明确传播，与 `read_page` 的重试不同）；批量使用情况未按页面拆分；不支持 `review_focus` 针对性审查；页面计数无上限；每条记录的 `finish_reason` 反映批量调用；手写批量发送页面级 `HandwritingPayload` 模式（`read_page` 包装为 `PageReviewPayload`）。
- 剩余验证（按设计未完成，归 Codex 所有）：对相邻测试套件进行更广泛的离线测试运行，以及由单独拥有的冻结基准驱动程序执行的任何真实模型实验 — 此过程未调用任何真实模型。
