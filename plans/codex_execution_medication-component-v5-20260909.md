# Codex Execution Plan: medication-component-v5-20260909

Objective: 仅实现隔离用药分项v5用途合同与合成测试，不接产品、不跑真实模型、不改临床数据

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 在scripts/medication_component_experiment.py和tests/v2/scripts/test_medication_component_experiment.py实现有原文依据的用途分类、用途条件校验与对账，保留不明药名实际使用、未知日期和分母；最小改动，先读owner决策，不读真实病例 | `runs/execution/medication-component-v5-20260909/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

Verify the two-file diff against the owner decisions in the execution context, synthetic regression results, then owner-run real isolated tests and separate review. Execution plus conference is justified by a bounded contract implementation and consequential medication/date attribution uncertainty. Neither this worker nor structural tests authorize formal ingestion. Primary-only remote execution avoids resources owned by the independent benchmark task.
