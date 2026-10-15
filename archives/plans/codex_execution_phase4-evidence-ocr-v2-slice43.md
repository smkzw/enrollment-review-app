# Codex Execution Plan: phase4-evidence-ocr-v2-slice43

Objective: 完成 Phase 4 Slice 4.3：建立不可变页产物与 OCR 持久化、逐格式分页和识别缓存、页级租约与全局8路准入、晚到结果拒绝、限定重试取消恢复及只读进度

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 实现0009_ocr_artifacts迁移、ORM与仓储：EvidenceProcessingRevision基础修订、页清单、OCRProfile、PageArtifact、OCRRun/Attempt/Page、原始请求响应工件、缓存唯一键、页工作租约及完整迁移反例测试 | `runs/execution/phase4-evidence-ocr-v2-slice43/worker_01.md` |
| `worker_02` | 实现逐格式分页与页产物生成、原生PDF文本坐标、扫描页路由、不可变页图/原始工件保存、OCRProfile指纹和页级缓存适配；只采用已冻结text-only路线，无真实坐标不画框 | `runs/execution/phase4-evidence-ocr-v2-slice43/worker_02.md` |
| `worker_03` | 将证据处理Job接入页级持久工作项、共享oMLX OCR门禁、租约代次与晚到拒绝、渲染背压、文件页检查点、限定重试取消恢复和SSE只读进度，并完成故障注入与多进程峰值测试 | `runs/execution/phase4-evidence-ocr-v2-slice43/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Workers execute strictly in order. After each worker, Codex reviews the real diff and focused tests before releasing the next boundary. Final acceptance requires migration/schema round-trip, immutable replay, format/page completeness, cache identity, stale-generation rejection, crash/restart/cancel/retry fault injection, shared-gate peak <= 8, full V2 regression, Ruff, Pyright and diff check. Slice 4.3 must leave evidence activation disabled and must not draw any red box without verified coordinates.
