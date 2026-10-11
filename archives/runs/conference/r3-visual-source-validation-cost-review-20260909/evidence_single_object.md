# Conference Output: r3-visual-source-validation-cost-review-20260909 - evidence_single_object

## Output

**审阅建议：暂不接受“批量路径与全量未批处理核验完全等价”的结论。** 当前源码存在保存点回滚失效缺口、缓存建立期间的版本绑定缺口，以及调用方绕过批量失效机制的长期成功缓存。

本轮按声明的 `codex-subagent / codex / gpt-6-astra` fallback 完成独立只读审阅。未调用或验证 `grok/grok-build/grok-4.6`，不声称 Grok 会话、运行回执或模型独立性已得到验证。未修改源码、创建报告、读取执行者报告或原始临床材料；报告由 runner 持久化。本意见不构成最终验收或临床签署。

### 1. 必须修复：保存点内建立的缓存可在回滚后继续命中

**证据**

`app/storage/page_review_visual_locator_validation.py:114–124` 的令牌仅包含根 Session 事务、连接代理身份、`data_version` 和 `total_changes`；没有嵌套事务身份。

`tests/v2/storage/test_page_review_visual_locator_batch.py:392–410` 只测试：

> 建立缓存 → 保存点内写入 → 回滚 → 再核验。

这时写入增加计数，确实能够失效；但未覆盖：

> 保存点内写入 → 建立缓存 → 回滚 → 再核验。

**推断与可复现路径**

后一个顺序中，回滚不会撤销或再次增加此前写入的 `total_changes`，根事务也未改变，因此回滚后的令牌可与缓存令牌相同。

可用合成夹具构造确定性反例：

1. 在外层事务将所选 metadata 的 `document_type` 镜像列改坏并 flush，保留原 payload。
2. 建立保存点，将镜像列恢复正确并 flush。
3. 核验合法 visual locator，缓存成功。
4. 回滚保存点，使镜像列再次与 payload 不一致。
5. 使用同一个 batch 核验：可跳过完整 metadata 闭包；不带 batch 的核验应拒绝。

完整路径会经过 `evidence_locator_repositories.py:3231–3248` 的 metadata 闭包；缓存命中则直接从 `page_review_visual_locator_validation.py:86` 返回。

这是新增复用机制的安全缺口，**不只是原全量路径的理论问题**。上述反例尚未在本会话运行。

**最小整改**

最保守方案：处于嵌套事务时不读取或保存缓存。或者将当前嵌套事务对象纳入令牌，并补充回滚、释放及多层保存点测试。不能仅依赖 `total_changes` 推断所有回滚均已失效。

### 2. 必须修复：读取后的令牌可能替旧证据标记新版本

**证据**

`page_review_visual_locator_validation.py:78` 在读取前取令牌，但 `89–97` 完成完整修订验证和来源构建后，直接使用新令牌存储，未比较读取前后的令牌。

**推断与可复现路径**

若另一个连接在完整 metadata 检查之后、最终令牌采集之前提交破坏 metadata 镜像的变更：

- 本次已经取得的 revision/source 仍来自旧状态；
- 新 `data_version` 却被写入缓存；
- 后续调用看见相同新令牌，可持续复用旧验证结果；
- 再次完整验证应发现损坏。

可在合成数据库中，通过来源构建返回前的测试同步点安排第二连接提交，随后比较同一 locator 的 batch 与非 batch 结果。应选择 metadata 等不会被后续逐定位读取再次检查的完整修订依赖。

原路径也可能存在多次读取间的并发窗口；**本次新增问题是把窗口内的旧验证结果缓存为更新后的版本，延长错误复用**。具体 SQLite 读事务模式对复现有影响，本会话未完成运行确认。

**最小整改**

只有读取前后令牌均有效且完全一致时才保存缓存。令牌变化或无法证明一致时，丢弃结果的缓存资格，回到完整路径；若要求本次结果也具有事务快照一致性，还需明确实际 SQLite 读事务与重试边界，不能只凭 `session.get_transaction()` 推定。

### 3. 调用方必须处理：成功定位集合绕过全部失效检查

**证据**

`app/storage/fact_authority.py:207–212` 虽为每次调用创建新的 batch，却通过实例级 `_validated_locators` 跳过之前成功的 locator。缓存键只有 authority JSON，没有事务或数据库代次。

`app/storage/fact_repositories.py:833–842` 的发布公共验证使用持有的 authority validator，因此不应默认 validator 永远只调用一次。

**确定性风险**

同一 validator：

1. 成功调用 `validate_locators(authority, ids)`。
2. 修改并 flush 该 visual locator 的 reconciliation/coverage，或损坏 locator。
3. 再次调用相同 authority/ids。

第二次循环为空，既不调用 `verify_visual_locator_authority`，也不采集版本令牌。即使再次执行完整 revision authority 验证，visual coverage/reconciliation 也不属于原 OCR revision 的定位成员闭包，不能依赖它补救。

**最小整改**

移除跨调用的成功定位集合，仅在本次调用内去重；保留本次调用的 revision batch。若确需跨调用复用，则该集合也必须受同等完整的失效机制约束。

本项是当前调用链真实缺口，但未取得此次优化前的精确冻结版本，**不将它武断归因于本次新增修改**。

### 4. 已保留的检查与其他边界

| 检查项 | 源码观察与限制 |
|---|---|
| 单会话绑定 | `page_review_visual_locator_validation.py:56–58` 明确拒绝跨 Session 使用。 |
| 逐定位结果 | batch 与非 batch 共用 `_load_verification_inputs`、`_materialize_and_compare`，保留完整 JSON 相等比较。 |
| 原始来源与权威 | cycle、coverage accepted 状态、reconciliation/review、authority 元组比较仍在路径中。 |
| pending ORM / autoflush | 令牌检查 new/dirty/deleted；前置 ORM 查询可能先 autoflush，此时写入计数应失效。`no_autoflush` 下仍有 pending 状态则不复用；缺少对应测试。 |
| 普通写入、根事务切换 | 已有 flush、SQL 写入、commit 和外部提交测试设计，但本会话未运行成功；不能替代保存点反向顺序测试。 |
| 非 SQLite / 探测失败 | 返回 `None` 后走完整路径；现有非 SQLite 测试只是修改 dialect 名称，不是真实后端兼容性证明。 |
| 连接身份 | 当前记录的是 `connection.connection` 代理的 `id`，不是明确持有的 `driver_connection` 身份。普通连接生命周期未发现直接反例；应修正文档措辞并补连接替换测试。 |
| 失败缓存 | 仅 revision/source 构建异常会清除 entry；前置检查和最终比较异常不会清除。与“失败不留下缓存”的文档不符，但缓存的是 revision 输入，单独这一点尚不证明错误 locator 被接受。 |
| ORM 外部刷新 | `PageReviewRepository` 使用 `Session.get`；调用仓储不保证绕过 identity map。外部提交测试主动 `expire_all()`，未证明有强引用 ORM 对象时能自动刷新。这是原完整路径也存在的边界。 |

错误方面，共用材料化函数保留 `ValueError → InvalidReferenceError` 转换及异常原因。`PersistedContractInvalid` 本身继承 `RuntimeError`，部分 gate 仅捕获 `RepositoryError`，因此损坏可能直接中止而不是形成 gate verdict；这同样不能直接列为 batch 新增回归。

### 5. 等价性与性能证据不足

现有测试有合法 coverage 相等、篡改拒绝和重建次数减少的检查，但仍不足以支持全流程精确等价：

- `test_gates_visual_batch_shared_across_candidates` 只比较 outcome 和排序后的 reasons，忽略返回的 affected scope；也没有比较完整 `batch_gate_evidence_closure` 输出。
- 缺少上述保存点反向顺序、构建期间外部提交、同一 validator 重复调用、pending/no-autoflush 的差分测试。
- `persist_visual_locators` 的计数测试使用已存在定位。新定位创建会 flush，导致 revision 缓存保守失效。
- `evidence_api_read_service.py:995–1000` 对 visual 定位另做未批处理权威核验，仍有重复开销。

方法调用次数减少不能证明 SQL 次数按同比例减少，更不能证明真实数据上的耗时改善。

**实际运行观察**

执行：

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -s -p no:cacheprovider tests/v2/storage/test_page_review_visual_locator_batch.py -x
```

首个测试在 fixture 初始化时因只读沙箱无法创建临时目录而失败：

```text
FileNotFoundError: No usable temporary directory found
1 error in 4.47s
```

**没有测试主体运行通过。** 这是环境阻断，不是产品测试失败；未尝试绕过沙箱或访问临床数据库。

### 6. 给 Codex 的整改与决策点

建议先修复保存点缓存身份、建立缓存前后版本一致性，以及调用方长期成功集合，再用合成数据库完成差分验证。比较应包括完整 coverage、异常类型及消息、完整 gate verdict 和 affected scope。

需要 Codex 明确两个有界问题：

1. 是否允许同一 `VisualLocatorBatchContext` 跨保存点使用？安全暂行方案是保存点期间禁用缓存。
2. 外部写入下的合同是“固定数据库快照内一致”，还是“每次调用重新看到已提交变更”？这决定是否必须同时处理真实读事务与 ORM identity map 刷新。未明确前，不接受“所有外部提交均安全失效”的描述。

初始 context/plan 中 source、scope 等仍为 TODO；本轮以用户提供的 quality gates 为实际合同。建议主会场补齐并绑定下面的源码版本。

### 7. 审阅版本绑定

以下为读取的当前工作树 SHA-256；未依赖执行者结论：

```text
app/storage/page_review_visual_locator_validation.py
90d75c01c0cf45a89dbe4b9c0ad674531d0d4b38566f634db9a4e1ba3fea9c65

app/storage/evidence_locator_repositories.py
e8b9ccec42876da717ed5ac14139ebd9b912d4bebe639d82b2829717c5e2d4d2

app/storage/fact_authority.py
71f269f6606a4db51f18f8032196739386302a3525748c02d1bb18a1bf064a08

app/domain/gates/fact_evidence_closure.py
a92a69ec159cbe4b416461b3ee4413f45bfcb5501ca787925c9f238045c08f71

app/services/page_review_visual_sources.py
73897acc2330ef7865c3f360c5e3430738f48cc7892813478bc28c70a9cd9304

tests/v2/storage/test_page_review_visual_locator_batch.py
f4935c304cbb6ffad3783c1ed69650823b4216b2bd398b2c5ee564bf273decd8
```

附加读取限于相关仓储、DB/session 工厂、来源关联服务、API 调用方及合成测试。没有执行临床来源核验、视觉验收或真实性能基准。
