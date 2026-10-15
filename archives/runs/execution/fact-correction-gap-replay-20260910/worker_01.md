所有证据已收集完毕。回滚的原子性已得到验证：失败后，仅剩下旧的事实（`120/80`），没有修正行，最新的 profile 仍然是修正前的那个。最终提交状态的验证运行已通过（`2 xfailed`）。

# 执行输出：fact-correction-gap-replay-20260910 - worker_01

## 边界与上下文检查

- 仅在运行器（runner）绑定的 worktree（`enrollment-review-app/.worktrees/phase5-clinical-facts-profile`）内工作。初始读取集（`context/fact-correction-gap-replay-20260910_execution_context.md`, `plans/codex_execution_fact-correction-gap-replay-20260910.md`）首先被读取；其他读取操作仅限于分配的源文件/测试范围以及上下文允许的相邻追踪。
- 唯一写入路径：`tests/v2/services/test_fact_correction_gap_reprojection.py`（通过文件写入工具创建，并对同一文件进行了一次编辑，以添加缺失的 xfail 标记）。没有修改任何产品、生产或生成文件。没有读取真实的生产数据——所有状态均位于临时的 SQLite 测试数据库中。没有模型/网络调用：校正执行器（correction executor）是确定性的。
- 未执行最终验收、会议或同行评审。所有工具使用情况记录在“命令与观察”中。

## 已执行工作

**1. 阅读（来源+测试）：** `app/services/fact_correction_service.py`, `app/services/fact_normalization_executor.py`, `app/services/evidence_expectation_projection_service.py`, `app/projections/evidence_expectations.py`, `app/domain/planning/fact_correction_impact.py` (planner + `_expand` expectation closure), `app/storage/evidence_expectation_repository.py` (API), fixture helpers (`tests/v2/storage/test_fact_correction_repository.py`, `tests/v2/storage/test_fact_repositories.py`, `tests/v2/helpers/phase5_fact_chain.py`, `tests/v2/services/test_fact_normalization_persistence.py`, `tests/v2/storage/test_fact_rule_link_repository.py`, `tests/v2/projections/test_evidence_expectations.py`), 现有的 `tests/v2/services/test_fact_correction_job.py`, correction executor/job service, patient profile service, v2 conftest。

**2. 在真实源中确认了两个缺陷假设：**
- **缺陷 A (非默认风险丢失导致升级)：** `_reproject_expectations` (`app/services/fact_correction_service.py:1290-1316`) 调用投影服务时使用了硬编码的 `gap_signals=[]`。原始终结流程（finalization flow）则通过 `_expectation_gap_signals` (`app/services/fact_normalization_executor.py:135-256`) 从已持久化的未解决项 + 拒绝的候选门（candidate gates）中推导出结构化的 `CoverageGapSignal`。因此，在人工校正（human correction）后，任何先前的显式 `ocr_or_parse_risk` / `observation_unverified` 风险都会丢失；完整的事实 + 空信号会重新投影为 `observed` / `source_coverage=complete` (`app/projections/evidence_expectations.py:286-297`) —— 导致 `observed_weak` 静默升级。
- **缺陷 B (无覆盖无信号导致回滚)：** 当校正移除了对到期模板（replacement-signature change → node scope）的最后覆盖时，重新投影在 `gap_signals=[]` 的情况下找不到任何观察结果；`project_expectation` 按设计抛出 `ProjectionInputError` (`app/projections/evidence_expectations.py:352-370`)，`apply_prepared_fact_correction` 将其转换为 `FactCorrectionError` (`fact_correction_service.py:1192-1204`)，执行器将其映射到 `FACT_CORRECTION_APPLY_FAILED` (`app/services/fact_correction_executor.py`) —— 导致整个合法的校正回滚。原始终结流程通过针对未覆盖的到期模板的后备（fallback-only）信号（executor lines 206-255）避免了同样的错误。现有的 `test_node_scope_recomputes_full_episode_projections` 从未显现这一点，因为其 fixture 链中没有播种期望模板（expectation templates）。

**3. 创建了 `tests/v2/services/test_fact_correction_gap_reprojection.py`** —— 两个严格定义的 xfail 期望行为回归测试，无猴子补丁（monkeypatching）：
- 使用真实的 `EvidenceExpectationProjectionService.project`（与终结流程相同的入口）播种初始预期；缺陷 A 的初始信号以真实的 `_expectation_gap_signals` 形式给出（具体的类型 + `applies_to_template_id`），这是“源运行中记录的风险”的最小合成等价物。运行真实了 `FactCorrectionJobService` + `FactCorrectionExecutor`。Docstrings 准确说明了哪些被复现，哪些没有（模型调用、队列并发，以及“校正记录其解决的未解决项”机制——该机制在产品中尚不存在）。
- 运行结果：`2 xfailed`，且失败点被证明位于缺陷断言处（详情见下文）。

## 制品与证据

- 制品：`tests/v2/services/test_fact_correction_gap_reprojection.py`（新文件，仅此文件）。
  - `test_correction_keeps_explicit_ocr_risk_and_does_not_silently_upgrade` — 在静默升级断言处 xfail (line 224)：实际为 `status=OBSERVED, gap_type=None, source_coverage=complete`。前置条件均已通过（作业 `completed`，校正已持久化，新事实值正确），隔离了预期丢失风险这一缺陷。
  - `test_correction_uncovering_due_template_completes_with_concrete_gap` — 在作业状态断言处 xfail (line 287)：`('failed_final', 'FACT_CORRECTION_APPLY_FAILED', [('plan','completed',None), ('apply','failed_final','FACT_CORRECTION_APPLY_FAILED')])`。
- **验证了回滚的原子性（不仅是推断）：** 一个内联诊断（无文件写入）复现了场景 B 并检查了失败的 apply 之后的数据库：事实值 = `['120/80']` (旧行保持)，校正行 = `0`，最新患者 profile = 校正前的那一个。
- **源运行链接（如何进行不可变选择 —— 报告项）：**
  - 校正谱系是只追加的 `FactCorrectionV2` (`correction_id`, `target_id ↔ new_entity_id`, 旧/新快照；`FactCorrectionRepository.list_by_authority / list_by_target(stable_identity) / list_by_review_episode`)。
  - 校正内容源运行：`target_id` → 目标实体行 → `run_id` → `FactNormalizationRunRepository.get`, `FactNormalizationCallRepository.list_by_run`, **`FactNormalizationUnresolvedItemRepository.list_by_run(run_id)`** (各行携带 `logical_document_id`/`page_numbers`/`affected_requirement_ids`/`affected_locator_ids`), 以及作为 OCR 风险来源的 `FactGateResultRepository` 中 `gate=transactional_publish, outcome≠accepted` 的行。
  - 新实体指向合成校正运行（`fcorr-run-*`，由 `_ensure_correction_run` 创建），其 `input_scope_sha256 = canonical_hash({"fact_correction_input/v1", correction_id, new_snapshot_sha256})` 绑定回校正：已发布事实 → fcorr 运行 → correction_id → 目标 → 原始临床运行，是一个封闭的两跳链。旧行从未被删除，因此取代（supersession）不会破坏该链接。
- **最小同源修复建议（证据-backed，供 Codex 决策）：**
  1. 将 `_expectation_gap_signals` (`app/services/fact_normalization_executor.py:135`) 提取到共享模块中，并让 `_reproject_expectations` 传入其结果，而不是 `gap_signals=[]` —— 一个推导，两个调用点。
  2. **选择，不要收集：** 仅从当前已发布活动事实（`fact.run_id`）的运行 ID 加上校正目标的源运行中获取未解决项/被拒绝的门信号。不要收集该片段的所有历史运行 —— 陈旧的信号会重新引发证据不再支持的缺口。
  3. **保留后备信号**（ investigator-assessment 模板使用 `observation_unverified`，否则使用 `record_incomplete`）适用于到期且未覆盖的模板：同源语义保证了缺陷 B 不可能发生；我的测试 B 固定了产生的具体缺口。
  4. **不要在没有证据的情况下携带前一个预期行的 `gap_type`** —— 该行是输出，而非证据；缺陷 A 的风险必须从源运行的不可变未解决项/门记录中重新推导得出，这些记录保留了该风险。这合理地避免了“多次运行/取代操作静默清除不确定性”的情况。
  5. 决策点（对 Codex）：校正是否应记录其解决的未解决项（校正 → unresolved_item 链接）。没有它，源运行的信号将保守地继续应用于已校正的事实 —— 这正是测试 A 所固定的期望行为。

## 命令与观察

- `.venv/bin/python -m pytest tests/v2/services/test_fact_correction_gap_reprojection.py -rxX --no-header -q` → **2 个 xfailed** (提交的状态；严格模式在意外 XPASS 时会报错)。
- 对每个测试执行 `.venv/bin/python -m pytest <test> --runxfail --tb=long` (仅诊断) → 失败位置如上文证据所述；前置条件断言均通过。
- 内联 heredoc Python 诊断 (临时 sqlite) → 证明回滚整洁度（引用的输出）。
- 所有运行均在 `.venv` (Python 3.12.13, pytest 9.0.2) 下从 worktree 根目录运行；每个测试都获得一个全新的迁移数据库（`tests/v2/conftest.py` 临时目录 fixture）。

## 阻碍或缺失环境

- 无。环境完全足够；分配的工作未受阻。

## 重运行请求或后续步骤

- 本次执行无需重跑。当修复落地后：从两个测试中移除 `@pytest.mark.xfail(strict=True)` 标记；如果 Codex 选择的修复方式使缺陷 B 的具体缺口类型与我固定的 `{record_incomplete, observation_unverified}` 不同，请调整该断言以匹配所选的同源语义。
- 剩余未验证（超出分配的最小范围）：来自具有模板范围（`applies_to_template_id=None`）的多个运行的信号行为，以及针对事件/暴露校正的相同推导（未测试；`_reproject_expectations` 处的修复入口点对它们是通用的）。
