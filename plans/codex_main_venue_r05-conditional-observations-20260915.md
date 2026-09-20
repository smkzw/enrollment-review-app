# Codex Main-Venue Plan: r05-conditional-observations-20260915

Date: TODO
Objective: 只读审阅条件性复查、发生次数和未来期间的最小完整消费设计。阅读 docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md §17、当前恢复计划T3、app/domain/contracts/rules.py、observation_selection.py、binding_qualification.py、app/domain/expression.py、app/services/qualified_binding_selection.py、app/services/ordered_observation_selection.py、app/projections/control_operand_calculation.py。核查当前occurrence/prospective忽略问题和新增UNKNOWN保护。重点提出复用既有来源资格/语义内容/冻结消费链的端到端路径，涵盖方案触发、许可、时限、初查复查关系、替代聚合、报告；不得以日期顺序或计数推定许可，不按项目/药物/疾病硬编码。具体列最小文件改动和未能完成的边界；不要新增孤立合同代替功能。用户禁止阶段测试：不写或运行测试、不import应用、不访问DB、不启动模型/浏览器/服务，不读workspace外临床资料，不修改源码。只可写指定会商报告，提供文件行号证据；源码审阅不是临床验收。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r05-conditional-observations-20260915/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
