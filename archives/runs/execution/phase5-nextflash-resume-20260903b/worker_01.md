# 执行输出：phase5-nextflash-resume-20260903b - worker_01

## 边界与上下文检查

- 在运行器绑定的当前工作目录内工作（Phase 5 worktree `codex/phase5-clinical-facts-profile`）。读取了两个初始上下文文件；分配的工作项是三个中的第 1 项（审计并最小修复 fact normalization 在已有成功 call/candidate 但 step checkpoint 缺失时重复调用模型的问题；新增恢复与幂等回归，禁止修改临床规则或运行数据）。
- 未读取或修改生产路径；未触及临床规则、门禁逻辑、规划层或任何运行数据/数据库；未安装软件包；未关闭工具。所有编辑均限于两个已被授权的 Phase 5 文件（在当前 worktree 中均已处于 untracked 状态，属于正在进行的 Phase 5 未提交工作的一部分）。
- 观察到 `app/workflow/jobstore.py` 中有 144 行预先存在的未提交插入（commit fence + parallel-wave 支持）；这些内容保持原样，我未对其进行任何改动。

## 已执行的工作

**根本原因审计（证据）：** 在 `app/services/fact_normalization_executor.py` 中，当 `context.last_checkpoint is None` 时，`execute_call` 总是重建模型输入并调用模型。复用仅作为 checkpoint-replay 分支存在。因此，对于任务载荷（job payload）中的调用标识（`call_id`/`run_id`/`logical_document_id`/`page_numbers`/`input_sha256`），如果其成功的 `FactNormalizationCallRecord`、候选（candidates）和未解决项（unresolved items）已经持久化，但步骤检查点（step checkpoint）丢失（中断运行、无 checkpoint 的恢复性重排队，或历史/已修复的行），恢复将不可避免地重新调用模型；由于模型输出是非确定性的，重放的 `apply()` 随后会因 `raw_output_sha256` 不匹配而触发致命的 `CALL_IDENTITY_CONFLICT` —— 导致作业无法合法完成（`apply()` 中的 call/candidate 身份保护，约第 858–869 行）。

**最小修复方案（仅限该文件）：**
1. 新增模块级辅助函数 `_rebuild_call_checkpoint_from_persisted(session, *, run_id, call)`：查找该调用的持久化调用记录；若不存在则返回 `None`（正常首次执行路径不变）；若标识不匹配则抛出 `CALL_IDENTITY_CONFLICT`（fail-closed）；若状态非 `SUCCEEDED`，或者不存在任何候选且不存在未解决项，则抛出 `PARTIAL_OUTPUT`（fail-closed）；否则根据持久化行重建步骤检查点字典（按位置排序的 `unresolved_items`，确定性的 `unresolved_items_sha256`，来自持久化调用的 `raw_output_sha256` / `completed_at`）。
2. `execute_call` 中的恢复分支（位于现有 checkpoint-replay 分支与模型调用路径之间）：重建检查点，然后通过现有的 `_load_frozen_agent_config`（冻结的提示词/模型配置完整性）和 `_validate_call_checkpoint_replay`（活动授权、运行授权匹配、行与检查点的标识/内容一致性）进行重新验证，并返回它——**不进行模型调用**。
3. 仅模块文档字符串（Module docstring）扩展了一句说明新契约的内容。

未对临床规则、门禁、规划、发布、jobstore/runner 或运行数据写入进行任何更改。

**回归测试（`tests/v2/services/test_fact_normalization_persistence.py`）：**
- 更新了 `test_duplicate_candidate_not_duplicated_on_retry` 为已修正的契约：在 `apply` 已提交且检查点丢失的情况下重新执行，现在返回重建的检查点，`transport_calls == 1`，`second == first.checkpoint`，无重复候选行。
- 新增 `test_lost_step_checkpoint_recovers_from_persisted_call_without_model_recall`：端到端 — 模型结果通过 `PreparedStepResult` 持久化，检查点/步骤完成事务从未发生；重新认领的运行器完成作业，期间**零额外模型调用**（transport raises if called），恰好 1 个候选，重建的检查点匹配，作业 `completed`，运行收敛于与直接路径相同的终端状态。
- 新增 `test_persisted_call_identity_conflict_fails_closed`：具有相同 `call_id` 但不同 `input_sha256` 的持久化调用 → `StepFailure(CALL_IDENTITY_CONFLICT)`，未调用 transport。

## 工件与证据

- `app/services/fact_normalization_executor.py` — 文档字符串（顶部）；新辅助函数 `_rebuild_call_checkpoint_from_persisted`（紧邻 `_verify_finalize_checkpoint_profile` 之前）；`execute_call` 中的恢复分支（在 `return dict(context.last_checkpoint)` 之后，模型调用 session 块之前）。
- `tests/v2/services/test_fact_normalization_persistence.py` — 覆盖范围文档字符串要点；`FactNormalizationCallRepository` 导入；1 个已更新 + 2 个新增测试（位于之前的 `test_duplicate_candidate_not_duplicated_on_retry` 位置）。
- 两个文件在 worktree 中均为 git-untracked（属于 Phase 5 未提交工作的一部分），因此无法生成最小化的 `git diff`；上述编辑位置即为精确变更点。

## 命令与观察结果

- `.venv/bin/python -m pytest tests/v2/services/test_fact_normalization_persistence.py -q` → **30 passed**（包含 1 个已更新 + 2 个新增测试）。
- `.venv/bin/python -m pytest tests/v2/services/test_fact_normalization_executor_profile.py tests/v2/services/test_fact_normalization_visual_observation_wiring.py tests/v2/services/test_fact_normalization_command_service.py tests/v2/services/test_fact_normalization_source_adapter.py tests/v2/services/test_fact_correction_job.py -q` → **61 passed**。
- `.venv/bin/python -m pytest tests/v2/workflow -q` → **84 passed**（runner/jobstore/recovery 未变动，完好）。
- `.venv/bin/python -m pytest tests/v2/services -q` → **353 passed, 1 skipped, 1 failed**；该失败（`test_evidence_processing_executor.py::test_native_pdf_creates_replayable_pages_without_external_ocr`，native-text 定位器断言）被证实为**原有且无关**：在物理上移除了我的两个文件后，该测试以同样的方式失败，且该测试未导入任何 fact-normalization 符号。
- `.venv/bin/python -m compileall` 于两个修改文件上 → OK；对这些文件执行 `git diff --check` → clean（仅 `.trellis/workspace/codex/journal-1.md` 中有预存的尾部空格标记，我未触碰该文件）。
- 确定性探针（草稿测试文件，运行后移除）：直接（非恢复）路径在使用相同的 `_candidate_fact` 测试装置（fixture）时以 `partial` 结束 — `value_unit_date_source rejected ['非数值事实不应携带单位']`，`transactional_publish rejected` — 因此恢复测试的 `partial` 断言是路径一致的，并在测试中附有解释性注释。

## 阻碍或缺失环境

- 无阻碍。预存在的无关失败（`test_evidence_processing_executor` 中的 native-PDF `native_text` 定位器断言）在此 worktree 中即可复现，且超出我的任务范围；已记录以供 Codex 分类。
- 环境说明：系统 `python3` 缺少 pytest；仓库本地的 `.venv` 拥有完整的工具链（已使用该环境）。

## 重跑请求或下一步

- 无重跑请求。该修复已准备好供 Codex 审查；它直接支持检查点的下一个安全操作（“验证首页组的幂等复用”）：在检查点丢失后恢复运行，现在将从持久化的成功调用中恢复，而无需进行另一次约 16 分钟的模型调用，也不会因致命的 `CALL_IDENTITY_CONFLICT` 而终止。
- 给 Codex 的一个精确问题（不阻碍我的任务）：对于非 `SUCCEEDED` 状态或没有候选/未解决内容的持久化调用，其 fail-closed 状态是预期的最终决定，还是您更希望在这些特定损坏状态下进行受控的重新调用？我实现的是 fail-closed（无静默重放），这符合模块的失效关闭（fail-closed）理念。
