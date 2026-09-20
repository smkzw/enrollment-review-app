# Codex Main-Venue Plan: r01-binding-input-check-20260913

Date: TODO
Objective: 只读审阅新增 app/domain/contracts/predicate_binding.py、app/services/predicate_binding_input.py、tests/v2/services/test_predicate_binding_input.py。对照设计§17.1.1和既有仓储真实定义，检查冻结输入是否完整保持规则逻辑、节点时间、事实对象与来源，是否有未发布内容混入、身份哈希缺失或校验被绕过。不写任何文件、不调产品模型、不读私人配置、不递归派发。务必给出可复现缺陷和代码行号；不是临床验收，不要只报测试通过。不重复主线程此前的论证。

## Task Decomposition

TODO

## Source Packet

TODO

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r01-binding-input-check-20260913/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

TODO: Record start/end time, pending/failed/incorporated status, retry reason, and whether late outputs were used.

## Codex Verification Checklist

TODO
