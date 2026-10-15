# Codex Execution Plan: acceptance-control-fixtures-20260916

Objective: 修复两个控制解构测试文件的现行合同夹具，使原有断言真正到达目标检查层，不放宽产品源码或测试不变量。仅授权测试文件和指定执行报告，不碰原始资料、数据库、模型服务。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 仅修改tests/v2/protocols/test_slice60zz_cross_stage_supplement_contract.py与tests/v2/protocols/test_slice61ab_candidate_repartition_contract.py，针对42项现有失败更新合法夹具，运行这两文件，明确产品缺陷而不绕过。 | `runs/execution/acceptance-control-fixtures-20260916/worker_01.md` |

## Codex Acceptance

Owner checks changes against pre-dispatch copies, preserves every original clinical/source invariant, reruns both files and adjacent source-restoration suite, and records remaining product defects. This packet has no clinical, model, browser or final product acceptance scope.
