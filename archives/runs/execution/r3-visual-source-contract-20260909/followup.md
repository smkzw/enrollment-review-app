全部通过 —— 67 个测试用例通过（23 个指定测试 + 44 个现有的关联/对账测试），边界已验证。最终报告：

# 执行输出: r3-visual-source-contract-20260909 - worker_01 (repair pass)

## 边界与上下文检查

同一会话的有界修复。仅对那两个被分配的文件进行了写入操作（`git status`：刚好有两个未追踪路径，`git diff --check` 为空白）。未更改其他任何文件；未触及 `ContractModel`；没有进行临床调用、数据库操作、凭据访问或网络访问。按照分配重新阅读了 `app/domain/page_source_association.py` (`source_aligned_fact_keys`, `_positioned_text` 语义) 和 `app/domain/contracts/page_review.py` (`association_text_sha256`, `ReconciliationConflict`)。

## 执行的工作

重写了 `app/domain/page_review_evidence_sources.py` (745 行) 和 `tests/v2/domain/test_page_review_evidence_sources.py` (647 行，23 个测试)。逐项修复如下：

1. **不可变性 + 重验证。** 本契约中的所有五个模型现在都设置为 `frozen=True`，并使用 `tuple` 字段 (`readings: tuple[X, X]`, `fact_sources/handwriting_sources: tuple[...]`)。由于上游页面审查契约对象没有冻结，且 `model_copy`/直接赋值绕过了它们的验证器，物化器现在**通过 `model_validate(model_dump())` 在入口处重新验证每个输入**（审查、对账、覆盖、关联来源）。模块文档字符串中说明了这一点：内容寻址加上绑定检查 —— 而非上游可变性声明 —— 才是溯源保证。全局 `ContractModel` 未动。回归测试：变异后的记录/对账（损坏的 `normalization_key`，损坏的手写 `raw_text`）现在会在验证器处失败，而不是传播（`test_materializer_revalidates_mutated_inputs_via_dumps`）；在已构建的来源上进行冻结赋值会引发异常。

2. **来源级与读数一致性。** `VisualFactSource` 现在要求每个读数的 `normalized_value/normalized_unit` 与其自身字段完全相等；`VisualHandwritingSource` 要求每个读数的 `kind/normalized_text` 与其自身字段相等。回归测试伪造了使用**重新计算 ID** 的来源级字段（`visual_fact_source_id` 接受了伪造的载荷），但构造仍然会被拒绝 —— 证明了哈希不是语义验证。

3. **通过现有关联实现的跨通道不同键对。** 根本原因已确认：`source_aligned_fact_keys` 通过定位范围 + 字段 + 不含位置的上下文键进行分组，因此对于同一接受的目标，两个通道可以携带不同的 `normalization_key`s（仅因 `location_text` 而异），而上游仅返回一个键集，从不返回对。现在物化器接收可选的 `association_source: PageAssociationSource`，并且：(a) 要求 `reconciliation.association_text_sha256 == source.text_sha256`（在缺失或不同时拒绝），(b) 要求文档/页面绑定，(c) **原样**重用 `source_aligned_fact_keys`（调用被封装，因此其错误会显现为 `PageVisualEvidenceSourceError`）作为配对资格，(d) 仅通过精确的同源标识（normalized 字段 + 不含 `location_text` 的 `observation_context_key` + value/unit + `source_arrow_marks`）将剩余键配对，要求每个目标恰好有一个未消耗的对应项。无模糊匹配。精确的同键模式保持不变。模式：来源级的 `normalization_key` 变为 `normalization_keys: tuple[str, ...]` —— 对于同键模式为一个条目，对于关联对为两个排序条目。**报告的边界：** 上游公开了键集，但未公开对，因此当相同的同源标识在多个来源范围命中时，配对不是范围精确的；此类页面会被保守地拒绝为“配对不唯一”（已进行回归测试）。范围精确配对需要重新实现定位循环，这为了避免使用不兼容的算法而未做处理。

4. **Bbox 溯源 + 真实摘录哈希。** 读数保留**原始观测值，包括模型提出的 bbox**（原始模型输出，记录为未验证）；坐标剥离现在仅存在于派生的 `VisualPageExcerptLocator` 中（`precision="page_excerpt"`，无坐标字段，`excerpt_sha256` 验证等于 `sha256(excerpt.encode("utf-8")).hexdigest()`），并且验证器要求定位器的摘录与原始观测摘录逐字对应。文本/图像哈希分离检查保留（`page_text_sha256 != page_image_sha256`）。测试断言 bbox 在观测值上被保留，在定位器中不存在，摘录哈希是真实的 sha256，并且 bbox 存在与否会改变内容地址（溯源是可寻址的），而派生的定位器保持不变。

5. **冲突矛盾 + ID 绑定。** 新的 `_check_conflicts_binding` 拒绝任何也出现在 `fact_conflicts` 中的已接受事实键或出现在 `handwriting_conflicts` 中的已接受手写键（现有契约允许的变异输入矛盾），并拒绝任何引用不在输入读取范围内的页面审查 ID 的冲突（检查 `fact`/`signal`/`handwriting` 冲突组）。回归测试：毒化的已接受键冲突、未知的审查 ID 冲突。

在记录中做出的有意决定：`contract_version` 保持为 `page-review-evidence-sources/v1` —— 该契约在此次修复前从未被持久化或接受，因此模式中断（`normalization_keys` 元组、`locator` 字段、元组读数、保留 bbox）是首次接受前的修订，而非已发布的演进。

## 工件与证据

- `app/domain/page_review_evidence_sources.py` (745 行, 新增, 未追踪)
- `tests/v2/domain/test_page_review_evidence_sources.py` (647 行, 新增, 未追踪)

## 命令与观察

- `.venv/bin/python -m pytest tests/v2/domain/test_page_review_evidence_sources.py -q` → **23 passed in 0.25s** (首次运行, 修复后)。
- 按照分配的现有套件：`.venv/bin/python -m pytest tests/v2/domain/test_page_source_association.py tests/v2/domain/test_page_review_contracts.py tests/v2/domain/test_page_review_evidence_sources.py -q` → **67 passed** (对账/关联语义未受影响)。
- `git status --porcelain` 过滤器：仅两个被分配的路径；`git diff --check`：干净。

## 障碍或缺失环境

无。

## 重新运行请求或下一步

对 Codex 的集成评审有两个如实的限制：(1) 范围精确的跨键配对 —— 现有的原语不公开定位/配对；多范围同源页面被保守地拒绝（`test_multi_range_same_identity_association_is_rejected_as_ambiguous` 记录了确切的情况），如果此类页面必须物化，则需要一个上游配对原语；(2) 溯源保证依赖于入口处的转储重验证加上内容地址，因为上游合同对象保持可变性。没有其他未解决的项目；分配的修复已完成，并通过上述确切的测试运行进行了验证。
