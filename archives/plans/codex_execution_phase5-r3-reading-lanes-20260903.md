# Codex Execution Plan: phase5-r3-reading-lanes-20260903

Objective: 落实R3受试者逐页判读读道边界：GLM与MiniMax双主读，Qwen3.8-Flash-Next仅手写第三读且只能写handwriting，消除旧降级主读表述并建立回归门禁。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只读审计设计书、实施计划和现有配置中的读道冲突，列出最小修订范围，不改临床数据。 | `runs/execution/phase5-r3-reading-lanes-20260903/worker_01.md` |
| `worker_02` | 以最小代码和测试固化读道、模型身份、输出权限和无temperature合同，不把新代码并入巨型模块。 | `runs/execution/phase5-r3-reading-lanes-20260903/worker_02.md` |
| `worker_03` | 运行聚焦回归并独立核对MTPLX不会进入主读、DeepSeek不进入读道、OCR仅作侧车。 | `runs/execution/phase5-r3-reading-lanes-20260903/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- `worker_01`：接受其文档漂移、main-B 凭据缺口和最小修订范围；按 2026-09-03 用户裁决将 Qwen 限定为手写第三读。
- `worker_02`：拒收 `page_review_lanes.py` 及其测试。原因：Phase 5 尚未收口、PageReviewRecord 合同尚未建立；实现达 400 行并把 cms-smk 抽象退化为 `minimax` 硬编码，还越界改变 Phase 5 共享 VLM 采样接口。相关文件已撤除，共享接口已恢复并通过聚焦回归。
- `worker_03`：接受其旧链路测试结果作为 Phase 5 基线；拒绝“Evidence Normalizer 就是未来 Page Reader”的范围推断。R3 双主读是 Phase 5.5 新增处理修订，不回改 Phase 5 当前规范化节点。
- Codex 已修订设计书与实施计划，删除 Qwen 主读降级和普通事实仲裁职责；清理前后证据见 `.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260903_R3_RECONCILIATION_AND_CLEANUP.md`。
- 验证：`.venv/bin/pytest -q tests/v2/llm/test_independent_vlm.py` 为 27 passed、1 skipped（联网门控按设计未启用）。本执行包不构成 Phase 5.5 实现或验收。
