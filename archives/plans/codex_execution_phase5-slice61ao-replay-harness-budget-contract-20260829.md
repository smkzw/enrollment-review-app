# Codex Execution Plan: phase5-slice61ao-replay-harness-budget-contract-20260829

Objective: 在不运行临床模型重放的前提下，将 p803-p805 不可变重放路径固化为可提交、可重现、不依赖人工矩阵的产品级 harness，并建立修订类串行后的明确预算合同与确定性验证。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 审计现有 p803-p805 临时重放脚本、产品执行链和不可变工件，输出最小可提交 harness 的复用路径、禁止依赖与验收点。 | `runs/execution/phase5-slice61ao-replay-harness-budget-contract-20260829/worker_01.md` |
| `worker_02` | 实现通用且项目无关的重放 harness，从原始 DOCX/PDF 产品结构化链构建指定稳定 source_ref 范围，保存不可变输入、输出和指纹，默认不调用模型。 | `runs/execution/phase5-slice61ao-replay-harness-budget-contract-20260829/worker_02.md` |
| `worker_03` | 建立串行修订类的预算合同与回归，防止默认2次在多类错误时产生偶然失败，同时保持严格上限、无限循环防护和不变输出。 | `runs/execution/phase5-slice61ao-replay-harness-budget-contract-20260829/worker_03.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

- [x] Human matrix and D001-specific gates excluded from product code.
- [x] Default path builds from raw DOCX without importing or instantiating transport.
- [x] Source hash and timestamp pinned before output; local paths excluded from pack bytes.
- [x] Actual whole-pack external fingerprint and checkpoint comparison supported.
- [x] Repair budget remains a strict global cap with class-by-class audit evidence and no-progress termination.
- [x] Focused 66 tests and full protocol 1026 tests passed.
- [x] Real D001 model-free double build is byte-reproducible.
- [ ] PDF-to-structure ingestion is not available and requires a separate product slice.
- [ ] Live p803-p805 replay is not authorized or executed in this slice.
