# 会议输出：r3-visual-cache-repair-review-20260909 - evidence_single_object

## 输出

### 0. 结论

**该限定增量可接受。** 三项审查维度（身份碰撞、失败原子性、来源验证）相对单条 `create` 均未被削弱，其中验证失败原子性严格强于逐条 `create`（预插入窗口内零落库）。两项遗留：① 裸 SQL SAVEPOINT 边界需以文档固化（仅 doc 改动）；② `create_visual_many` 自建批量上下文在混合新旧定位的持久化中多付一次整修订重建（纯成本，可选）。另确认你对我上一轮“直接返回 artifact”建议的否定是正确的，并收回我上一轮对裸 SAVEPOINT 的错误断言（见 §3、§4）。

### 1. 三项削弱审查（证据与行号）

**身份碰撞 —— 未削弱。**
- 对库检查不变：`_prepare_create`（evidence_locator_repositories.py:652-671）逐条执行与旧 `create` 相同的重复编号检查（:653-659）与 occurrence 身份碰撞查询（:662-671）。
- 批内碰撞是新增风险面，已闭合：`create_visual_many` 先拒绝批内重复 `locator_id`（:643-644）。这一检查充分的前提是视觉定位的身份条件退化为 `locator_id` 等值（:324-326），而该前提由“仅接视觉定位”守卫（:641-642）保证——这两个约束互为支承，不可只保留其一。
- 语义层还有一层加固：`persist_visual_locators` 对同编号不同合同的重复投影显式拒绝（page_review_visual_sources.py:33-34）。

**失败原子性 —— 未削弱，验证阶段严格更强。**
- 验证失败于第 K 条：`_prepare_create` 只做读操作、返回未 `add` 的记录对象（:721 `return created`），前 K-1 条无任何 session 写入；`add_all` 在全部验证之后（:648）。`test_create_visual_many_rejects_invalid_batch_before_any_insert`（test:80-90）以“第一项不落库”直接断言。
- flush 失败/decode 失败：单次 `_flush_guarded`（:649）与逐条 create 的失败位置等价——decode 在 flush 之后（:650），失败时行已 flush 但未提交，由调用方事务回滚，和单条 `create` 尾部 `self.get` 的失败位置一致。
- 与单条 create 的一处真实不对称（非缺陷）：批量路径插入后只 decode+镜像校验，不再跑 `_verify_source`。论证成立：视觉验证的全部输入（cycle probe、coverage、reconciliation、reviews、修订闭包、page association sources）**不读 `EvidenceLocatorArtifactRecord`**——flush 只写这一张表，重验只会对相同输入跑第二遍；且 INSERT 抬高 `total_changes` 使任何后续批上下文失效重验。此论证同样依赖 :641 的 layer 守卫（见 §5.3）。

**来源验证 —— 未削弱。**
- 每条定位仍各自通过完整 `_verify_source(artifact, batch)`（:661），`verify()` 内 coverage/reconciliation/reviews/cycle probe 逐条新鲜读取（page_review_visual_locator_validation.py:134-154），修订级输入经 token 守护共享一次重建——全部验证先于唯一一次 flush，验证之间无写，复用合法。`test_create_many_new_visual_locators_validates_before_writes`（test:68-77）断言恰好 `revision_get=1、association_build=1` 且 `get_many` 回读等价。
- 单条 `create` 外部行为未变：仍为 `_prepare_create` + add/flush + 尾部**全量**回读（:636）。

### 2. 上一轮更正确认

我上轮建议“`create` 尾部直接返回入参 artifact”确实不成立：它只消除当条的尾部重建，但第 K 条的 INSERT 抬高 `total_changes` 后，第 K+1 条的 `_verify_source` 仍会失配重建，N 条首写仍是 N 次整修订核验。你采取的“整批验证与插入分离”（验证全过 → 一次 `add_all`/flush → 仅 decode）使批内零中间写、复用全程合法，是结构上正确的修法。成员查询修复（fact_authority.py:234-243）与我上轮建议一致（`WHERE snapshot_id` + 严格 `expected_snapshot_id`），后续 Python 过滤变冗余但无害，校验严格性反而增强。

### 3. 裸 SQL SAVEPOINT：收回我上轮的断言

你指出的场景成立，我上轮“裸 SAVEPOINT 下任何改行写都会抬高 `total_changes`、旧缓存仍被失效、语义仍保守正确”的结论**不完整**。它只覆盖“缓存先于保存点内写入建立”的方向；反方向存在真实缺口：外层脏写 W → 裸 `SAVEPOINT s`（`session.execute(text(...))`，非 `begin_nested()`）→ 修复写 R → flush → 此时 `in_nested_transaction()` 为假（ORM 不感知）→ token 有效 → 缓存以“W+R 已修复状态”入库 → 裸 `ROLLBACK TO s` 撤销 R，而 `total_changes` 不因回滚下降（W、R 在执行时已计入）→ 回滚后 token 与缓存 token 仍相等 → **基于修复态的过期缓存被复用于未修复态**。这正是 `test_valid_savepoint_cannot_cache_state_restored_invalid_by_rollback`（test:437）的场景，仅因该测试走 ORM `begin_nested()` 使 `in_nested_transaction()` 为真才被拦截。

### 4. 当前边界与最小固化建议

保证范围应表述为：**仅覆盖 ORM 跟踪的事务**（`session.begin()` / `begin_nested()`，`_snapshot_token` 的 `in_nested_transaction()` 检查，page_review_visual_locator_validation.py:117）。产品写路径确实全部经 ORM 事务（db.py 模块契约“应用服务在最外层持有 `with session.begin()`”），故产品自身代码内守门完整；绕过 ORM 的裸 SAVEPOINT/ROLLBACK TO 不在保证范围内，不应声称“任意 SQL 可靠”。

最小修复（仅文档，两处各加一句）：模块 docstring（:1-12）与 `_snapshot_token` docstring（:105-115）目前写"nested rollback ... forces the full verification / Savepoints disable reuse"而未限定“ORM 跟踪”，建议明确写入：“仅覆盖 ORM 事务与 ORM 保存点；绕过 ORM 的裸 SQL SAVEPOINT/ROLLBACK TO 不在复用安全保证内，产品写路径必须使用 ORM 事务”。代码不变。

### 5. 残余小项（不阻塞接受）

1. **成本（可选）**：`create_visual_many` 总是自建批量上下文（:645）。混合新旧定位的 `persist_visual_locators` 中，elif 分支已把调用方 batch 预热，批量写再自建上下文会多付一次整修订重建。允许传入可选调用方 batch 可消除；保持内部自建则是更保守的生命周期选择，二者皆可，建议记录取舍。
2. **空批**：`create_visual_many([])` 与 `persist_visual_locators` 全已存在路径下传空列表——守卫通过、`add_all([])`/flush 空转，无害，无需改。
3. **未来扩展警告（重要）**：若日后把 :641 的 layer 守卫放宽到 raw_ocr/native_text/effective_text，本增量的两条不变量必须重新推导——非视觉层的 occurrence 身份条件**会读** `EvidenceLocatorArtifactRecord`，批内碰撞不能只靠 `locator_id` 去重；建议在该方法加一行 docstring 说明“仅视觉层”的原因（身份=编号 + 验证输入不读工件表），防止未来放宽时无声破坏。
4. 22 项测试计数已核对（新增 2 项恰为首写单重建与失败原子性）；真实 8 定位 25.86s→3.28s 为所有者陈述，与代码路径一致但我未运行（只读授权），不作为全例/临床通过的证据——你方不据此声称是正确姿态，我同样不据此采信超出只读等价性的结论。

### 6. 未验证项

- 未运行任何测试与真实数据计时（只读授权；仅静态走读 + 测试断言与代码行为逐条比对）。
- §1 中“验证输入不读工件表”为对六类输入读取路径的静态枚举结论（sourced 自代码，未做运行时追踪）。
- 未读取病例数据库、个人配置，未调用模型，未修改任何文件；本报告由所有者持久化。
