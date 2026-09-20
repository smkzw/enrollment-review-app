# 执行输出：r3-visual-source-contract-20260909 - worker_01

## 边界与上下文检查

- 在运行器绑定的 worktree `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile` (branch `codex/phase5-clinical-facts-profile`) 内工作。仅创建了两个授权文件；未修改其他任何文件 (`git status --porcelain` 显示正好有两个新的 `??` 条目)。
- 初始读取集：`context/r3-visual-source-contract-20260909_execution_context.md`, `plans/codex_execution_r3-visual-source-contract-20260909.md`。
- 读取集之外，读取了以下只读来源（依据上下文的真值来源列表）：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` §3.3/§4.2/§7.2, `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` (§8 来源关联实施补充), `app/domain/contracts/page_review.py`, `app/domain/contracts/facts.py`, `app/domain/contracts/evidence_locator.py`, `app/domain/contracts/common.py`, `app/domain/contracts/evidence.py` (BoundingBox), `app/domain/page_reconciliation.py`, `app/domain/page_source_association.py`, `app/domain/page_normalization.py` (签名), `app/projections/page_review_sources.py`, `app/domain/publication.py` (`canonical_hash`), `app/domain/contracts/clause_pack.py` (ID 模式), 测试夹具 `tests/v2/domain/test_page_review_contracts.py`, `tests/v2/domain/test_page_review_candidate_sources.py`。
- 未调用临床模型，未访问凭据/数据库/原始临床记录，未使用网络工具，未进行生产写入，未进行安装。

## 已执行工作

实现了 **`app/domain/page_review_evidence_sources.py`** (553 行) —— 一种不可变、内容寻址的视觉来源契约，以及一个 **纯物化器 (pure materializer)**：

- **`VisualFactReading` / `VisualHandwritingReading`** —— 针对每个已接受观察的单通道（per-lane）字面绑定：保留 `lane`、`page_review_id`、`provider/model/reasoning_effort`、`prompt_version`、`response_sha256` 以及完整的原始观察（精确的 `region.excerpt`、原始文本/值、上下文）。模型建议的 `bbox` 会被读取验证器拒绝；物化器会剥离坐标并重新验证观察结果，因此视觉精度始终为 `page_excerpt`，且摘录永远不需要是 OCR 子串。
- **`VisualFactSource` / `VisualHandwritingSource`** —— 针对每个已接受目标，恰好绑定两个读取，且仅限于 main-A + main-B；`(provider, model)` 身份重复的通道会被拒绝（相同的模型不是独立的双读取）；针对读取内容（按通道排序）的确定性 ID `visual-fact:<32hex>` / `visual-handwriting:<32hex>`；针对 `normalized_value/unit` / `normalized_text` 的跨通道相等性检查。
- **`PageVisualEvidenceSourceSet`** —— 页面级集合，绑定 `page_artifact_id / source_document_version_id / page_number / page_image_sha256`、`clause_pack_id+sha256`、`reconciliation_id`、`coverage_id` 以及来自覆盖范围的 `evidence_snapshot_id + evidence_processing_revision_id`（现有的快照/处理权限）。可选的 `page_text_sha256`（OCR sidecar 文本版本哈希）是唯一的文本哈希字段，并验证是否 `!= page_image_sha256` —— 图像哈希永远不能进入文本哈希字段。集合 ID `visual-source-set:<32hex>` 是确定性的，排除了 `created_at`，并且对每个绑定和每个来源 ID 敏感。
- **`materialize_page_visual_evidence_sources(reviews, reconciliation, coverage, *, page_text_sha256=None)`** —— 纯函数，无存储/写入，**未发明第二种对账算法**：它仅消耗现有的 `PageReconciliation` 输出，并执行绑定前置条件检查（通道计数/标识、页面/文档/图像/包标识、对账页面/包/审阅 ID 绑定、覆盖处置=ACCEPTED + 对账 ID + 包绑定）。仅物化 `accepted_fact_keys` 和 `accepted_handwriting`；子句信号/NONE/冲突/单读者内容在结构上被排除（集合仅具有事实和手写来源列表）。每个已接受的键（或手写代表性对象）在字典上必须与每个通道的一个观察匹配 —— 键存在但没有实际匹配证据的陈旧对账会被拒绝；与任何通道观察都不相等的篡改手写代表对象会被拒绝（物化器不进行任何合成）。

实现了 **`tests/v2/domain/test_page_review_evidence_sources.py`** (393 行，仅合成夹具，重用了来自 `test_page_review_contracts` 的现有 `_review_payload/_fact/_handwriting` 夹具)。所有必需案例的 15 个测试：稳定的内容寻址（审查顺序和 `created_at` 不变性）、原始摘录保留，包括非 OCR 子串的视觉摘录、对更改的响应哈希 / 摘录 / 覆盖绑定敏感、重复模型身份拒绝、通道页面图像/文档漂移拒绝、对账页面/审阅 ID/包绑定拒绝、陈旧的已接受键拒绝、篡改的手写代表对象拒绝、覆盖强制执行（缺少条目、错误的文档、已丢弃的处置、错误的对账 ID、错误的包）、子句独占页面 → 空集合且任何地方都没有子句负载、冲突/单读者内容未物化、bbox 剥离（添加模型框既不会出现在输出中，也不会改变内容 ID）、文本/图像哈希分离，以及合同级别验证器测试。

## 工件与证据

- `app/domain/page_review_evidence_sources.py` (新增，未追踪)
- `tests/v2/domain/test_page_review_evidence_sources.py` (新增，未追踪)
- 测试证据：`15 passed in 0.19s`，使用项目 venv 运行。

## 命令与观察

- `apply_patch` 用于创建/编辑（按项目惯例）；确认可用。
- `.venv/bin/python -m pytest tests/v2/domain/test_page_review_evidence_sources.py -v` → 首次运行 11 个通过 / 4 个失败；所有 4 个失败均为测试侧的 bug（小写 `normalized_text` `"ncs"`、`_pair` 元组解包错误、重复通道案例触发了对账自身的防护而非物化器的防护、覆盖变异应当断言不同的 ID 而非异常）。修复后：**15 个通过**。
- `git diff --check`（针对这两个文件）→ 空格整洁。仅包含指定测试文件，按指示执行；未运行更广泛的测试套件。
- 观察：`handwriting_normalization_key` 会小写 `normalized_text` ("NCS" → "ncs") —— 已在断言中体现。`fact_normalization_key` 将规范化的上下文哈希嵌入到键中，因此相等的键已经暗示了相等的规范化的上下文/值/单位标识；物化器保留了跨通道相等性检查，作为针对非确定性键的廉价深度防御。

## 障碍或缺失环境

无。环境完整（`.venv` 包含 pydantic 2.13.3, pytest 9.0.2）。

## 重新运行请求或下一步

给 Codex 的一个设计交互，用于集成审查（推理，按设计不变更）：对于对账通过源对齐路径接受了一个键的情况，当该键在通道中出现了**两次**（在不同位置出现相同值）时，物化器会以“多个候选观察，无法唯一绑定来源目标”拒绝该页面 —— 因为它仅接收对账对象，而不接收关联源，因此无法推断哪个通道内的观察构成了已接受的对。这与契约的“已接受目标的实际匹配证据”要求一致；如果必须物化此类页面，所有者集成应传递一个配对提示（或关联源哈希）作为附加的显式输入。目前：拒绝是保守且明确的。

其余整合需求（如实报告，超出此数据包范围）：数据库持久化、`reconcile_page_reviews`/覆盖率生成路径中的连线，以及需要拥有者评审的任何 UI/表面使用；根据指示，该契约目前是附加的且未连接的。无需重新运行；分配的工作项已完成，并已通过指定的测试文件验证。
