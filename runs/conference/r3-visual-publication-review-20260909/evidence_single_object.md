审阅完成。以下为完整会议报告（按输出模式返回，不写运行器管理的报告路径）。

# Conference Output: r3-visual-publication-review-20260909 - evidence_single_object

## Output

### 结论（TLDR）

完整接线在「双读对账 → 物化 → 定位持久化 → Normalizer 输入 → 候选校验 → 门禁 → 发布 → 回放」各环节本身闭合良好（基线 37 项视觉相关测试通过，我另跑了隔离合成全链验证发布成功），但**「原件回查/Profile 呈现」最后一环断裂**：视觉定位发布成功后，Patient Profile 全部读取端点对含视觉定位的档案一律抛 `AppInternalError`（HTTP 500）。我用隔离合成环境完整复现（复现脚本与输出见 D1）。这是本次最高优先级缺陷。次级问题为页级重建的冗余成本（已量化）与两处呈现层小缺口。

---

### D1（高危，已实证）：视觉定位发布成功后，Patient Profile 读取全线 500

**证据（代码链）：**
- `app/api/v2/patient_profiles.py:77-84`：`_revision_dto` 把 `profile_locator_ids(revision)` 交给 `locators_by_ids(..., complete_processing_revision_id=...)`；`latest`/`history`/按 ID 读取三条路由都走它。
- `app/services/evidence_api_read_service.py:983-987`：`outside = set(ordered_ids) - set(complete.locator_ids)`，非空即抛 `AppInternalError("病历档案的证据定位与冻结资料版本不一致，无法安全打开原文。")`（`status_code=500`，`evidence_app_errors.py:202-204`）。
- 视觉定位按设计**永不进入** `complete.locator_ids`：`persist_visual_locators`（`app/services/page_review_visual_sources.py:21-31`）只写 `EvidenceLocatorArtifactRecord`；防循环检查在 `page_review_visual_locator_validation.py:21-24` 明确禁止把视觉定位追加进 `ProcessingRevisionLocatorRecord`。
- 但发布链处处放行视觉定位：门禁 `fact_evidence_closure.py:378-389` 把核对通过的视觉定位并入合法集合；`fact_authority.py:210-213` 的 `_validate_locator` 视觉分支直接 `return`（不查修订成员表）；`fact_publication_service.py:123-126` 把候选 `locator_ids` 并入发布实体；`app/projections/patient_profile.py:118` 起档案条目 `locator_ids=sorted(set(fact.locator_ids))`。

**实证（隔离合成测试，临时目录数据库，未触碰工作树/生产路径）：** 复刻 `tests/v2/services/test_page_review_visual_sources.py::test_visual_fact_publishes_through_product_job` 后追加读取步骤，输出：
```
job ran: True
published facts: 1
  fact locator_ids: ['visual-locator:6d9864819d97da1c18ca379b36f18471']
profile revision: 1 status: ProfileStatus.SUCCEEDED
profile locator ids: ['visual-locator:6d9864819d97da1c18ca379b36f18471']
DEEPLINK FAILED: AppInternalError 病历档案的证据定位与冻结资料版本不一致，无法安全打开原文。
```
即：产品作业成功、事实发布成功、档案生成 `SUCCEEDED`，随后该受试者的 Profile 当前版/历史版/按 ID 读取全部 500。现有测试恰好停在发布断言（`test_page_review_visual_sources.py:161-165`），未覆盖读回，故未被发现。设计裁决（`docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §2026-09-09）明确「统一在事实发布和原件呈现处消费」，此环属既定范围。

**最小修复建议：** 在 `locators_by_ids` 中对 `outside` 集合逐个取定位，`source_layer == PAGE_REVIEW_VISUAL` 时按门禁同款规则核验（`verify_visual_locator_authority` 或等价的 coverage 元组与 revision 作用域比对：`evidence_processing_revision_id`/`evidence_snapshot_id`/`review_episode_id` 三者相等即收编进返回映射），其余层维持现行为。不修改档案合同、不改发布链。同时补一条「视觉定位发布 → Profile 读取 → 深链 DTO 含视觉来源」的回归测试。

### D2（中危，已量化）：页级重建冗余成本随页数×事实数放大

**证据（实测计数，1 个已采信页 + 1 条事实 + 2 读道 = 2 个视觉定位）：** 一次产品级作业全流程 `materialize_page_visual_evidence_sources` 执行 **13 次**、`reconcile_page_reviews` 3 次、`page_association_sources` 3 次。构成：
- 任务创建期 6 次物化：`persist_visual_locators` 重建一次 + 每个定位 `repository.create` → `_verify_source`（`evidence_locator_repositories.py:599-601`）再各重建一次，加上 `create_or_reuse_from_source` 逐调用算 scope 哈希的 `build_evidence_normalizer_input`（`fact_normalization_job_service.py:328-346`、`fact_normalization_source_adapter.py:545-546`）。
- 执行/发布期：每个候选定位在门禁与 `FactAuthorityValidator.validate_locators` 各触发一次**整页**重建（`page_review_visual_locator_validation.py:37-44`），`_validated_locators` 缓存按 locator_id 而非按页（`fact_authority.py:200-203`）。
- 每次重建还加载完整修订闭包 + 全部 OCR 页与校对（`page_association_sources` 遍历整个 manifest），且 `rebuild_visual_sources` 重建**全部**已采信页后才按 `wanted` 过滤（`fact_normalization_source_adapter.py:544-546`）。

**推断：** 每页 F 条事实 ≈ 创建期 1+2F 次整页重建，发布期再 2F 次；页数与调用数线性相乘。单机单用户下不破坏正确性，但真实文档（数十页、每页数十观察）会让发布阶段出现数百到上千次整页重对账，与「检查冗余重建成本」的审阅范围直接相关。

**最小修复建议：**（1）会话内按 `coverage_id`（或 entry）memo 已重建的 source set / 已核验定位——所有输入不可变，事务内缓存安全；（2）给 `rebuild_visual_sources` 增加页过滤参数，`build_evidence_normalizer_input` 只重建本次调用页；（3）`FactAuthorityValidator` 的视觉分支复用同一 memo。另注（非视觉引入但同热路径）：`_validate_locator` 非视觉路径对每个定位全表加载并解码 `EvidenceSnapshotMemberRecord`（`fact_authority.py:229-238`），建议一并按快照过滤。

### D3（低危，呈现层）：视觉定位的标签与溯源未进 DTO

**证据：** `app/api/v2/vocabulary.py:362-366` 的 `LOCATOR_SOURCE_LAYER_LABELS` 无 `page_review_visual` 条目，`locator_source_layer_label` 回退显示原始枚举串；`locator_dto`（`evidence_processing_schemas.py:142-188`）不投影 `page_review_visual` 溯源（source_set_id/coverage/page_image_sha256），且视觉定位 `ocr_page_id=None`（契约强制，`evidence_locator.py:393-394`）。**推断：** 修复 D1 后前端会拿到视觉定位，但无法区分呈现「页级双读摘录」，也不能用 `ocr_page_id` 导航（须走 `/evidence-processing-revisions/{revision_id}/pages/{entry_id}/image`，按 page_artifact_id/页码解析）。**最小修复：** 补标签（如「页级双读摘录」）+ LocatorDTO 增加可选 `page_review_visual` 溯源块；前端原件打开逻辑不得假设 `ocr_page_id` 非空。

### D4（边界核对，无缺陷）：交叉验证通过的关键不变量

以下为证据级确认（非推断）：摘录哈希与页图哈希分立（契约 `evidence_locator.py:401-407` + 物化器 `page_review_evidence_sources.py:348-349,562-563`）；旧文字修订零改写（`test_page_review_visual_sources.py:49-50` 字节级断言，我重跑通过）；防循环（`page_review_visual_locator_validation.py:21-24`）；回放失效关闭且策略版本受控（`fact_normalization_replay_sources.py:16-25` + 测试）；跨键配对仅精确同源身份、多重命中拒绝物化（`page_source_association.py:60-71`、`page_review_evidence_sources.py:454-457`）；视觉模式下条款信号不得作为候选来源（`page_review_sources.py:44-45`）；任务幂等键缝合视觉策略且无观察旧载荷字节不变（`fact_normalization_job_service.py:440-479`）。基线聚焦测试 37 项全过。

### D5（低危，错误分类）：覆盖不一致时任务创建报 500 而非定向错误

**证据：** `persist_visual_locators`/`rebuild_visual_sources` 抛裸 `ValueError`（`page_review_visual_sources.py:31,48` 等），`create_or_reuse` 的异常翻译只识别 `FactPlanningSourceError/FactAuthorityError/InvalidJobDefinitionError`（`fact_normalization_command_service.py:562-575`）。**推断：** 覆盖或判读记录不一致时操作者收到通用 500，无处置指引。**最小修复：** 将这些 `ValueError` 归一为领域错误类型并接入翻译（或复用 `FactPlanningSourceError`）。

### 对 Codex 的质疑、决策点与有界问题

1. **Q1（阻断 D1 修复方向，需裁决）：** `locators_by_ids` 收编「已核验视觉定位」是否接受？我建议按门禁同款三元组比对收编（D1 方案），而非在档案构建期过滤掉视觉定位——后者违背「原件呈现处统一消费」的裁决。若同意，是否同时把 `page_review_visual` 溯源加入 LocatorDTO（D3）？安全临时路径：未裁决前，视觉模式任务仍可创建发布，但需知晓 Profile 读取会 500。
2. **Q2（政策确认）：** 覆盖模式下选择性视觉观察通道被静默停用——`fact_normalization_job_service.py:313-321` 在 `page_review_coverage_id is not None` 时 `attachments=()`，已成功的 selective-vision 观察既不进输入也不进运行范围哈希。这是「双读取代单读」的既定决策还是遗漏？设计文档该节未提及此压制。若为既定决策，请在裁决记录补一句；否则属于证据通道静默丢失。
3. **Q3（性能预算）：** D2 的每定位整页重建在单机单用户规模是否可接受至下一阶段？我建议至少落地 coverage 级 memo（改动小、无行为变化）；页过滤参数可作为后续项。
4. **对计划的质疑：** 主会场计划文件（`plans/codex_main_venue_r3-visual-publication-review-20260909.md`）的任务分解/核对清单均为 TODO，本轮审阅实际以会议上下文的来源清单为准；建议 Codex 在终局记录里补齐该文件，避免后续回放缺少对照。

### 证据与不确定性声明

- 证据：上述全部文件行号引用、37 项基线测试结果、两个隔离合成探针（深链复现 + 成本计数，脚本位于 `/tmp/conf_visual_deeplink_probe.py`、`/tmp/conf_visual_cost_probe.py`，临时目录数据库，未改工作树、未读凭据、未调用模型）。
- 推断：D2 的规模放大外推、D3 的前端导航假设（前端代码不在本次来源清单内，未核对）。
- 不确定性：未运行全量测试套件（仅聚焦视觉相关 4 个文件）；前端对 `ocr_page_id` 的实际依赖未验证；D1 修复方案未做补丁级验证（只读约束）。
- 未验证项与原因：生产路径按边界未读；真实病例模型按约束未调用。

（本报告为会议参与者输出，不构成最终临床/视觉/用户验收；Codex 保留最终裁定权。）
