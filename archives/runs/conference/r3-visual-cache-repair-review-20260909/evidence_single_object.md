读集与必要的直接依赖已全部核对完毕（含 WAL 配置、合同基类、`create`/`get_many` diff、`materialize` 复制语义、主会场计划）。审阅证据已充分，以下为完整报告。

# Conference Output: r3-visual-cache-repair-review-20260909 - evidence_single_object

## Output

### 0. 总体结论（先说结果）

四项指定核查点（保存点、前后 token 比较、授权校验跨调用、失败失效/pending 语义）经独立代码走读**均成立**，缓存复用的守门条件（同事务对象 + 同 DBAPI 连接 + `data_version`/`total_changes` 不变 + 无 pending + 非嵌套 + SQLite 方言）在逻辑上闭合。但发现 **1 个重要成本缺陷（A：批量 `create` 路径每条插入都使缓存失效，首次持久化 N 条视觉定位实际做 N+1 次整修订核验，且现有测试因预先建好定位而未覆盖该分支）**、1 个同链路剩余无界成本（B：文本定位授权校验全表扫描快照成员），以及 3 个低危一致性观察（C/D/E）。均不构成正确性回归，但 A 直接削弱本次“成本修复”在主写入路径上的目标。

### 1. 审阅范围与证据基线

- 直接审阅：`app/storage/page_review_visual_locator_validation.py`（新文件，未提交）、`app/storage/fact_authority.py`、`app/storage/evidence_locator_repositories.py`（定位仓储与完整修订仓储）、`app/domain/gates/fact_evidence_closure.py`、`tests/v2/storage/test_page_review_visual_locator_batch.py`。
- 必要依赖：`app/services/page_association_sources.py`、`app/domain/page_review_evidence_sources.py`（materialize）、`app/services/page_review_visual_sources.py`（persist/rebuild）、`app/storage/db.py`（WAL、`expire_on_commit=False`）、`app/domain/contracts/common.py`、`app/domain/page_source_association.py`。
- 运行环境事实：SQLAlchemy 2.0.52（pyproject.toml:15）；WAL 模式 + `synchronous=FULL`（db.py:41-48）；sessionmaker `expire_on_commit=False`（db.py:126）。
- 修复面确认（git diff HEAD + untracked）：`fact_authority.py` 与 `evidence_locator_repositories.py` 的 diff 显示本修复新增了 visual 定位路由（`_verify_source` → `verify_visual_locator`）、batch 贯穿 `create/get/get_or_none/get_many`、`validate_locators` 批内共享上下文、`_validate_complete_revision` 由轻量 decode 改为完整闭包 `get`。
- 未运行任何测试（只读授权；pytest 会写入缓存产物）。20 项测试全部计数核对（恰为 20 个测试函数），按所有者通过采信，仅作为有限证据。

### 2. 指定核查项裁定

**(1) 保存点内建立缓存后 rollback 是否仍可能复用 —— 不会复用（成立）。**
- 保存点期间不可能新建缓存：`_snapshot_token` 在 `session.in_nested_transaction()` 时直接返回 None（page_review_visual_locator_validation.py:117），`_revision_and_page_source` 对 token=None 既不命中也不存储（:84-89、:99-100）。
- 保存点前已存在的缓存条目：保存点内首次 `verify` 会先 pop（:91）再全量重建且不回存；即使保存点内从未调用 verify，其中的任何改行写都会永久抬高 sqlite3 `total_changes`（该计数自连接打开起只增不减，rollback 不回退——Python sqlite3 文档语义），回滚后 token 必然失配 → 强制全量。`test_nested_rollback_forces_full_reverification`（test:392-410）覆盖前者。
- 理论残余（推断，非缺陷）：绕过 ORM 的裸 SQL `SAVEPOINT`（`session.execute(text("SAVEPOINT ..."))`）不会使 `in_nested_transaction()` 为真；但其中任何改行写同样抬高 `total_changes`，旧缓存仍被失效，纯读保存点不改变数据。语义仍保守正确，只是缺直接回归固化（见 §4 缺口 3）。

**(2) 缓存构建前后 token 比较是否正确 —— 正确（成立）。**
- before-token 在构建前取（:82），after-token 在构建后取（:98），`token is None or after_token != token` 即不入库（:99-100）：构建期间发生的任何代次变化（同连接写、pending 出现、进入嵌套、连接更换、外部提交导致的 `data_version` 变化）都会取消缓存资格。`test_changes_during_source_build_do_not_qualify_cache`（test:435-457）直接覆盖。
- 命中路径 `cached.token[0] is token[0] and cached.token[1:] == token[1:]`（:87-88）与存储路径的元组 `!=`（:99）语义一致：`SessionTransaction` 无自定义 `__eq__`，`==` 即同一性。`id(dbapi_connection)` 的地址复用风险被 token[0]（事务对象同一性）阻断——同一事务内 DBAPI 连接对象唯一且存活。
- `_snapshot_token` 的取值顺序安全：先查 pending/嵌套（:117）再取事务（:119-121），`session.connection()` 时事务已存在不会隐式开新事务；`PRAGMA data_version` 走 Connection 层执行（:128）不触发 Session autoflush，pending 检查不会被 autoflush 洗掉。
- WAL 细节（推断，两种语义下均安全）：WAL 下 `data_version` 在本连接处于读快照内是否即时反映他连接提交，SQLite 文档存在微妙性；但若 PRAGMA 看到新值 → 不缓存/失效（保守方向），若读快照固定 → 同一事务内的全量重建读到的也是同一快照，缓存与全量结果等价。跨事务复用被 token[0] 阻断，故该不确定性不影响结论。

**(3) FactAuthorityValidator 重复调用是否重新检查定位 —— 是（成立）。**
- `validate_locators` 每次调用新建 `VisualLocatorBatchContext(self.session)`（fact_authority.py:206），批内共享、随调用结束丢弃；重复调用对每个 locator 重新执行 `_validate_locator`（视觉定位走 `verify_visual_locator_authority` 完整核验，:215-218）。`test_authority_revalidates_same_locator_on_later_call`（test:460-473）以 monkeypatch 反证。无跨调用跳过。

**(4) 失败失效与 pending/no_autoflush 语义 —— 成立。**
- 构建抛异常 → pop + raise（:95-97）；物化比对抛异常 → `verify` 的 except pop（:73-75）；token 无法证明新鲜 → 返回但不存储（:99-100）。“失败不留下缓存条目”在代码层面成立。
- pending（`session.new/dirty/deleted` 非空）→ token None → 全量且不缓存（:117）。验证读触发的 autoflush 只会把代次推向更保守方向（失效/不存），不会造成假命中。拒绝不污染上下文（`test_tampered_locator_rejected_before_and_after_reuse` 末段，test:196-197）。

### 3. 实质性问题与最小修复建议

**A（重要，成本 + 覆盖缺口）：批量 `create` 路径每条插入必然使缓存失效，首次持久化 N 条视觉定位执行 N+1 次整修订闭包 + 来源重建，而非 1 次。**
- 机制：`EvidenceLocatorRepository.create` 先 `_verify_source(artifact, batch)`（evidence_locator_repositories.py:641，此处可存缓存），随后 `session.add` + `_flush_guarded`（:703-704）——INSERT 抬高 `total_changes`——尾部 `return self.get(artifact.locator_id, batch=batch)`（:705）的 token 必然失配 → pop + 全量重建。逐条推演：N 条全新定位共享 batch 时首次 create 2 次重建、其后每条尾部 get 再各 1 次，合计 N+1（无 batch 时为 2N；目标是 1）。
- 影响面：`persist_visual_locators`（page_review_visual_sources.py:28-32）首次写入路径（生产主路径）逐条调用 `create(locator, batch=batch)`，正是关联执行任务 `r3-visual-source-validation-cost-20260909` 的目标场景。
- 测试掩盖：`test_persist_visual_locators_shares_batch`（test:171-183）的 `_setup_visual` 已预先 `repository.create(locator)` 建好全部定位（test:62-64），`persist_visual_locators` 只走 `elif` 已存在分支，create 分支成本从未被测量。
- 最小修复建议（二选一）：① `create` 尾部改为不触发 `_verify_source` 的回读——decode + 列镜像校验后直接返回（入参工件在同一调用内刚通过完整来源核验，INSERT 只写入其自身编码）；② 直接返回入参 `artifact`。同时补一条回归：全新定位批量 create 断言 `revision_get == 1`、`association_build == 1`。
- 这是本报告最高影响缺陷：不修复则修复目标“同一事务内重复的整修订核验只执行一次”（get_many 与 validate_locators 的 docstring 承诺）在写入路径不成立。

**B（中，性能，属同链路既有问题）：文本定位授权校验对快照成员全表扫描 + 全量解码，且逐定位重复。**
- fact_authority.py:234-243：`session.execute(select(EvidenceSnapshotMemberRecord)).scalars().all()` 无 WHERE，取出所有 episode/所有快照的成员行并在 Python 侧逐行 `_decode_member_record` 后过滤。`validate_locators` 对 N 个文本定位执行 N 次全表扫描。该段在本次 diff 中未改动（既有），但本次修复的主题即该授权链路的成本，视觉侧已批量化、文本侧仍无界。
- 最小修复：加 `.where(EvidenceSnapshotMemberRecord.snapshot_id == authority.evidence_snapshot_v2_id)`，并把 `_decode_member_record(row, expected_snapshot_id=authority.evidence_snapshot_v2_id)` 传严；与 fact_evidence_closure.py:102-105 已有按 snapshot_id 过滤的写法对齐。过滤后成员集合与现行 Python 过滤结果等价，行为保持。

**C（低，一致性观察）：`fact_evidence_closure._fetch_cached` 的 locator_cache 缓存“已验证的解码合同”，无 token 守护。**
- fact_evidence_closure.py:198-211：批内首次 fetch 时验证通过后，后续 candidate 直接复用合同、不再重验。若批处理中途发生外部提交篡改（WAL 下同进程可见），`visual_batch` 会因 `data_version` 失效重建修订级输入，但 locator_cache 中的定位合同不会重验——与非批处理路径（每次 `repo.get` 全验）不完全等价。缓解：`batch_gate_evidence_closure` 单次调用内无写、单用户本地单线程，现实风险低。
- 最小修复建议：当 visual_batch 条目失效时同步清空 locator_cache，或在两处 docstring 固化“批内无写”前提。

**D（低，健壮性观察）：缓存共享对象为可变 pydantic 模型，缺冻结防护。**
- `_CachedVisualRevision.sources/.revision`（page_review_visual_locator_validation.py:25-33）中的 `PageAssociationSource`/`CompleteEvidenceProcessingRevision` 均非 frozen（ContractModel 仅 `extra="forbid"`，common.py:11-12；materialize 侧自注“上游合同未冻结”，page_review_evidence_sources.py:513 并以 `model_validate(model_dump())` 防御性复制，:514-520）。当前所有消费者只读、无现实污染；但未来任何消费者就地改写 `source.text`/哈希将污染同批后续定位，且 token 无法察觉纯内存变更。
- 最小修复：命中路径返回 `source.model_copy()`（单页小对象，成本可忽略），或冻结 `PageAssociationSource`。

**E（提示，等价性边界）：跨会话篡改检测强度受身份映射新鲜度限制（非本次修复引入）。**
- db.py:126 `expire_on_commit=False`；`test_committed_mutation_in_other_session_does_not_pass` 显式 `first.expire_all()`（test:338）后才断言拒绝。若不 expire，token 失效后的全量重建同样会从身份映射读到旧对象——缓存路径与全量路径在此等价（无回归），但“失效后必然检测到篡改”的实际强度以此为先决。建议在模块 docstring 注明。

**F（流程）：** `plans/codex_main_venue_r3-visual-cache-repair-review-20260909.md` 的 Date/Decomposition/Source Packet/Checklist 全部为 TODO；会议上下文的 Source Of Truth 与 Scope 亦为 TODO。不影响本报告代码结论，但 Codex 验收清单缺失。

### 4. 回归覆盖核对（20 项）与缺口

已核对测试文件恰含 20 个测试，覆盖：结果等价（1）、重建计数削减（2,3,19,20）、持久化共享（4）、篡改拒绝（5-8,11,12）、循环拒绝（9）、跨会话拒绝（10）、SQL 直写+提交失效（13）、保存点两向（14,15）、构建期变更（16）、授权跨调用重验（17）、非 SQLite 降级（18）。与我独立推导的守门机制一致，采信为有效证据。

缺口（按重要度）：
1. 全新定位批量 `create` 的成本与失效行为（问题 A）——零覆盖。
2. 保存点回滚后 `batch._entries` 状态的直接断言（test:392-410 仅断言 rebuild 计数=2；test:413-432 覆盖反向场景；建议补 `assert batch._entries == {}`）。
3. 裸 SQL SAVEPOINT（非 `begin_nested`）下 total_changes 兜底语义的直接测试。
4. locator_cache 与 visual_batch 失效联动（问题 C）。
5. `effective_text` 定位经 `_verify_effective_text`（evidence_locator_repositories.py:597-598 未接收 batch）逐条重跑完整闭包——属批量化未覆盖的相邻来源层，建议至少记录为后续成本任务。

### 5. 给 Codex 的决策点与有界问题

- Q1（对应 A，需决策）：`create` 尾部的全量回读是否为刻意的“写后自证”？若刻意保留，请确认接受首次持久化路径 N+1 次整修订核验的成本；否则建议采纳 §3-A 的最小修复并补回归。安全临时路径：维持现状不影响正确性，仅成本。
- Q2（对应 C）：locator_cache 失效联动是否纳入本次修复范围，或登记为后续任务？我的建议是登记后续（单用户本地、批内无写，风险低）。
- Q3（流程）：主会场计划的验收清单为空，请 Codex 在最终验收前补齐，以便逐项对账。

### 6. 未验证项与证据等级

- 未运行测试套件（只读授权），20 项通过为所有者陈述 + 静态逐条核对其断言与代码行为一致。
- sqlite3 `total_changes` 只增不减、rollback 不回退：文档语义（sourced fact）；WAL 下 `data_version` 读快照内的可见性细节：推断，已论证两种语义下结论不变（inference）；N+1 次重建的推演：基于代码路径与 token 机制的静态推演（inference，未实测计数）。
- 未读取临床资料、运行数据库与个人配置；未修改任何文件；本报告未写入 runner 管理的报告路径，由所有者持久化。
