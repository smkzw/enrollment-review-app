I'll start by reading the execution context and plan, then locate where segment-capability checkpoint recovery is implemented so the adversarial tests can target the right behavior.
The production files look restored; next I'll map existing adversarial coverage and what's still missing for checkpoint recovery.
Next I'll add a dedicated adversarial test file for the checkpoint-recovery scenarios that aren't fully covered yet.
Non-compact prompts append extra text after the JSON, so I'll fix the test transports to parse only the first JSON object.
The test file was truncated, so I'm rewriting it completely with the fixes applied.
# Execution Output: phase5-segment-capability-checkpoint-recovery-20260901 - worker_03

## Boundary And Context Check

- **Role**: `worker_03` — 独立编写并运行对抗测试；**未修改任何生产实现**。
- **工作目录**: `.worktrees/phase5-clinical-facts-profile`（授权 worktree）。
- **已读上下文**: `context/phase5-segment-capability-checkpoint-recovery-20260901_execution_context.md`、`plans/codex_execution_phase5-segment-capability-checkpoint-recovery-20260901.md`、`worker_01.md`、`worker_02.md`。
- **边界遵守**: 仅新增测试文件；未触碰 D001 / 冻结临床源 / 旧探针产物；未改 `app/` 生产代码。

**观测（证据）**: `worker_02` 报告曾记录 `git checkout` 事故，但当前树中 `protocol_deconstructor.py`（4483 行）、`deepseek_protocol_transport.py`（537 行）、`protocol_deconstruction_executor.py`（1216 行）均含 `supports_parent_rule_segmentation` / 段级 checkpoint 实现，对抗测试可针对现树运行。

---

## Work Performed

1. **只读追踪**现有分段/checkpoint 实现（`protocol_deconstructor.py:3334-3805`、`deepseek_protocol_transport.py:272-280`）及既有测试（`test_parent_rule_semantic_segmentation.py`、`test_deepseek_protocol_transport_slice3.py`）。
2. **独立新增**对抗测试套件 `tests/v2/protocols/test_segment_capability_checkpoint_recovery.py`（726 行，13 个用例），覆盖任务要求的全部维度：
   - GLM 可进入分段（`supports_parent_rule_segmentation=True` 且 `uses_compact_wire_contract=False`）
   - 非分段传输不误入
   - 成功段 checkpoint 复用
   - 仅恢复失败段（超时 1 次重试 + 成功段缓存）
   - 缓存身份漂移失效（`prompt_template` / `protocol_file_sha256` / `semantic_cache_identity`）
   - 超时 vs Schema 错误分类
   - 双超时 fail-closed
   - 并发硬顶（99→3）
   - 部分段失败不发布合并结果（整父回退）
   - 项目特异硬编码扫描
3. **运行测试**并修复非 compact prompt 解析问题（测试 helper `_payload_from_segment_prompt` 使用 `JSONDecoder.raw_decode`，因非 compact 路径在 JSON 后附加原文 prose）。

---

## Artifacts And Evidence

| 产物 | 路径 | 说明 |
|---|---|---|
| 对抗测试套件 | `tests/v2/protocols/test_segment_capability_checkpoint_recovery.py` | 13 用例，全新文件 |
| 生产实现（只读引用） | `app/agents/protocol_deconstructor.py` | `_supports_parent_rule_segmentation`、`_collect_parent_segment`、`_semantic_batch_cache_key` |
| 传输能力（只读引用） | `app/agents/deepseek_protocol_transport.py:277` | GLM `supports_parent_rule_segmentation=True` |
| 缓存契约（只读引用） | `app/services/protocol_deconstruction_executor.py:168-174` | `store(..., cache_contract=...)` |

**测试覆盖矩阵**:

| 要求维度 | 测试函数 |
|---|---|
| GLM 可进入分段 | `test_glm_transport_declares_*`, `test_glm_style_transport_enters_*` |
| 非分段不误入 | `test_non_segment_transport_skips_parent_segmentation` |
| 成功段复用 | `test_successful_segment_is_reused_from_checkpoint` |
| 只恢复失败段 | `test_only_failed_segment_is_retried_*` |
| 缓存身份漂移失效 | `test_cache_identity_drift_invalidates_*` (×3 参数化) |
| 超时分类 | `test_timeout_is_classified_separately_from_schema_invalid` |
| 失败关闭 | `test_double_timeout_fails_closed_*` |
| 并发上限 | `test_segment_collection_respects_concurrency_hard_cap` |
| 合并完整性/不发布 | `test_partial_segment_failure_does_not_publish_merged_parent` |
| 硬编码扫描 | `test_segmentation_recovery_modules_contain_no_project_specific_hardcoding` |

---

## Commands And Observations

```bash
.venv/bin/python -m pytest tests/v2/protocols/test_segment_capability_checkpoint_recovery.py -v --tb=short
# 13 passed in 0.32s

git status --short tests/v2/protocols/test_segment_capability_checkpoint_recovery.py
# ?? tests/v2/protocols/test_segment_capability_checkpoint_recovery.py  (仅新增，无生产改动)
```

| 观测 | 类型 | 说明 |
|---|---|---|
| 13/13 对抗测试通过 | **证据** | 针对当前树实现 |
| 非 compact segment prompt 在 JSON 后有 prose | **证据** | 需 `raw_decode` 解析；compact 路径无此问题 |
| GLM 分段路径经 `_collect_initial_semantic_response` 完整 4 段合并 | **证据** | `test_glm_style_transport_enters_*` |
| 段超时仅重试 1 次（`calls == 2`） | **证据** | `test_double_timeout_fails_closed_*` |
| 身份漂移后 cache miss 触发二次 `start` | **证据** | 参数化 drift 测试 |
| worker_02 事故报告与当前树状态不一致 | **推断** | 文件已在事故后恢复；对抗测试基于现树 |

---

## Blockers Or Missing Environment

1. **无阻塞** — 对抗测试已全部通过。
2. **推断**: `worker_02` 的实施/恢复状态需 Codex 单独确认；本 worker 仅验证**当前树**行为，不替代 live GLM 探针验收。
3. **未运行**: live GLM 网络探针、全量 `test_parent_rule_semantic_segmentation.py` 回归（非本 worker 范围，但建议 Codex 验收时一并执行）。

---

## Rerun Requests Or Next Step

**给 Codex 的验收命令**:

```bash
.venv/bin/python -m pytest tests/v2/protocols/test_segment_capability_checkpoint_recovery.py -v
.venv/bin/python -m pytest tests/v2/protocols/test_parent_rule_semantic_segmentation.py -q
.venv/bin/python -m pytest tests/v2/protocols/test_deepseek_protocol_transport_slice3.py -q
```

**Resume point**: 对抗测试已交付且通过。若 `worker_02` 仍有未合并的生产修复，Codex 应在合并后重跑上述三条命令；live GLM 分段探针（EX-06 硬停策略）仍为独立验收项，不由本对抗套件替代。
