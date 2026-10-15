# Execution Output: written-judgment-search-contract-20260910 - worker_01

## Boundary And Context Check

- 本轮扩权仅新增两个文件：`app/services/judgment_search_source.py`、`tests/v2/services/test_judgment_search_source.py`（`git status` 确认五个未跟踪文件 = 既有三个合同文件 + 本轮两个新增；既有三个合同文件本轮零改动——复审后**未发现**需要报告的具体不可或缺缺陷）。
- 无网络/模型/依赖/凭据/真实临床库/API 接线/委派；无 fallback、无本地平台激活。`apply_patch` 在本运行时不存在——如实披露：全部新文件由 ZCode Write 工具创建，本报告不作与 apply_patch 的等价性声明。
- 勘察过的既有边界（只读）：`app/storage/repositories.py`（`EpisodeRepository`、`list_expectation_templates`、`save_expectation_templates`、`get_rule_set`、`AppendRepository`/`WORKFLOW_STAGE_CONFIG`、`persist_fixture`）、`app/storage/evidence_locator_repositories.py`（`CompleteEvidenceProcessingRevisionRepository` 全部闭包方法）、`app/storage/ocr_repositories.py`（`PageArtifactRepository.get`）、`app/services/fact_normalization_source_adapter.py`（权威-修订一致性既有模式）、`app/services/evidence_api_read_service.py`（活动指针读取模式）、`app/domain/contracts/ocr.py`（`PageArtifact`，`page_image_sha256` 可空）、种子助手 `tests/v2/helpers/phase5_fact_chain.py` → `tests/v2/services/test_fact_normalization_persistence.py::_seed_chain`、`tests/v2/storage/test_fact_rule_link_repository.py::_seed_rule_set_revision2`、夹具 `contracts/v1/fixtures/subject-*.json`。

## Work Performed

**`build_judgment_search_scope(session, authority, requirement_id)`（只读构建器）按序执行：**

1. **活动权威核对**：`EpisodeRepository.get` 读取审核节点成对活动指针（活动快照 + 活动完整修订），与 `FactAuthority` 逐项一致，陈旧即拒（`JudgmentSearchSourceError`，"活动指针不一致"）；episode 的 project/subject/rule-set 作用域与权威元组交叉核对（拒绝跨身份）。
2. **requirement 归属**：`list_expectation_templates(session, rule_set_id, rule_set_revision)`（既有已验证边界，镜像全验后按真值筛选）按 requirement_id 过滤，必须**恰好一条**；缺失/跨规则集/重复均为有界错误（消息含命中数）。
3. **完整修订来源闭包**：`CompleteEvidenceProcessingRevisionRepository.get()` 读取时全量验证——**从代码核实其保证**（`get` → `_verify_page_mirror`/`_verify_assoc_mirror`/`_verify_referenced` → `_verify_page_closure`（页清单精确等于每快照成员资料的持久化页集合，对照 `SourceDocumentVersionV2Record.page_count` 与 PageArtifact 行，缺页/多页/换页拒绝）→ `_verify_terminal_successful_pages`（逐页终态成功页产物 + 终态成功 OCR 页 + 归属一致）→ 元数据/风险/定位/候选绑定闭包 → 完成清单哈希按子记录 payload 重算）。构建器**未复刻**该大校验器，只做防御性身份再核对。
4. **逐清单页身份绑定**（纯函数 `scope_page_identity`）：`PageArtifactRepository.get` 解码页产物，核对资料版本/页码与清单条目一致、页图哈希非空；缺失页图或外来身份 → 有界错误，绝不虚构哈希、绝不静默省略。**不读取 `entry.status`**——无任何页状态/日期/文件类别/对账采信过滤。
5. 排序与哈希全部来自新合同（`order_key` 排序 + `judgment_search_scope_sha256`）；清单序保证文档连续页码升序，页工件 ID 不保证随页码单调，故按合同序显式排序。

**从代码核实的边界事实（如实声明，不过度声称）：**
- **页数完整性可证**：仓储闭包证明清单页 = 每个快照成员资料版本的持久化页集合（page_count 已知时为 1..page_count 交叉核对）。
- **“失败 OCR 但有渲染图”的页在当前完整修订合同下结构性不存在**：`_verify_terminal_successful_pages` 要求每页终态成功页产物 + 终态成功 OCR 页。构建器因此不可能在该范围遇到此类页；其无状态过滤立场由纯函数测试证明（DEGRADED/FAILED 清单条目 + 合法页产物 → 原样纳入）。若未来修订合同允许此类页，构建器无需改动即纳入。
- **范围 ≠ 临床完整性**：范围只证明“活动修订供给了这些页”，不证明临床要求的全部外部文件均已供给；`source_scope_verified` 恒 False；无 professional_judgment 生产者。
- 完成清单哈希（`manifest_sha256_for`）覆盖 base/页条目/定位/风险/校对/元数据/被提及资料等子记录 payload，**不含** PageArtifact 载荷——因此页图哈希篡改可穿过仓储闭包、由构建器自身检查兜底（对应测试）。

## Artifacts And Evidence

**测试（10 项，全部真实临时 SQLite + 既有仓储，无手工注入临床答案）：**
- `test_page_identity_binds_entry_and_artifact_exactly`（纯：身份绑定逐字段）
- `test_missing_page_image_is_bounded_error_without_fabrication`（纯：合同合法的 FAILED 页产物（image=None）→ "页图哈希"有界错误，非虚构非省略）
- `test_foreign_artifact_identity_is_bounded_error`（纯：归属资料版本/页码不一致 → 拒绝；页工件 ID 是查找键不作被核对属性）
- `test_entry_status_is_never_a_filter`（纯：DEGRADED/FAILED 条目 + 合法产物 → 纳入，证明无状态过滤）
- `test_build_scope_complete_authoritative_and_stable_hash`（完整非空权威范围；预条件断言模板恰好一条；页字段与 DB 页产物逐一相等；哈希重算一致；跨会话重建 `==` 相等、哈希稳定）
- `test_build_scope_is_read_only_and_mutates_nothing`（全库逐表行指纹前后相等 + `session.new/dirty` 为空）
- `test_stale_authority_pointers_are_rejected`（陈旧修订指针/陈旧快照指针 → “活动指针”；异规则集 → “作用域”）
- `test_missing_or_foreign_requirement_is_rejected`（未知 ID 命中 0；纯空白拒绝；外来 requirement（仅存在于 revision 2，经 `_seed_rule_set_revision2` 真实落库）命中 0）
- `test_multipage_scope_includes_all_manifest_pages`（测试内按同一仓储边界构建**两页**完整修订链——现有共享夹具仅单页，此缺口已用真实多页链闭合；两页均入范围、合同序、哈希一致）
- `test_artifact_tampering_is_bounded_error_without_silent_omission`（篡改页产物页码（列+payload 一致重编码，可穿过完成清单）→ 构建器边界抛 `RevisionClosureError`，有界、无静默省略、无虚构哈希）

**模板经既有已验证边界落库**（`_seed_templates`）：夹具 workflow stages 命名空间化为 `{rule_set_id}:{revision}:` 前缀 → `AppendRepository(WORKFLOW_STAGE_CONFIG)` 落库 → `project_evidence_expectation_templates` 投影 → `save_expectation_templates` 保存（其内部作用域门禁全走通）。

## Commands And Observations

- 新测试首跑 5 失败/5 通过，均为测试侧问题并已修正：`PageArtifactRecord` 实际在 `app.storage.ocr_models`；FAILED 清单条目不得携带 OCR 引用（合同正确拒绝）；SQLAlchemy 2.x 无 `engine.table_names()`（改 `inspect().get_table_names()`）；两处测试模块路径笔误（`tests.v2.services` 而非 `storage`）；“删除工件行”变体被 SQLite 外键约束阻止——**该约束本身就是“工件行不会缺失”的存储级保证**，改由篡改变体覆盖，删除变体已移除并在此说明。
- `.venv/bin/python -m pytest tests/v2/services/test_judgment_search_source.py -q` → **10 passed**。
- `.venv/bin/python -m pytest tests/v2/services/test_page_review_job_service.py tests/v2/domain/test_judgment_search_coverage.py tests/v2/domain/test_phase5_fact_contracts.py tests/v2/domain/test_page_review_evidence_sources.py -q` → **107 passed**（page-review job planning 套件 + 合同覆盖 31 + 既有 73）。
- `git status --porcelain`（限定五文件）→ 三个合同文件保持 owner 复跑 104 项时的原样，仅新增两个授权文件。

## Blockers Or Missing Environment

- 无阻断。工具披露：`apply_patch` 不可用，新文件经 ZCode Write 创建，无等价性声明。
- 边界披露（非缺陷）：完整修订合同结构性排除失败/降级 OCR 页（`_verify_terminal_successful_pages`，已从代码引用）；“失败 OCR 含渲染图纳入范围”因此在真实仓储路径不可构造，以纯函数测试 + 无状态过滤实现 + 本声明覆盖。工件行删除被外键约束阻止（存储完整性保证）。

## Rerun Requests Or Next Step

- 无需重跑。仍为必需且**未**实现（本轮无变化、无声称）：产品双读检索执行与检索结果持久化/回读核对、条款级判断缺失报告生产者、真实模型与原件验证、临床采信链路。构建器未接任何 API/服务调用方；`build_judgment_search_scope` 当前无产品调用点。
