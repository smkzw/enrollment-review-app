# Execution Output: phase5-slice58d-d001-control-matrix-20260825 - worker_01

## Boundary And Context Check

仅修改授权合同与测试路径；未读取或修改 D001 工件，未改变 Agent draft/hydrated 语义。

## Work Performed

- 在 `StructureUnitDisposition` 增加 `linked_procedure_candidate_id`。
- 强制流程处置只能绑定正式目录身份或候选身份之一。
- 候选身份统一要求 `candidate:`/`candidate-`/`candidate_` 前缀，并拒绝 IN/EX/REQ/CTRL 伪官方形态。
- 矩阵候选流程严格校验：
  - 处置必须为 `REQUIRED_PROCEDURE`；
  - 候选字段必须与矩阵 `source_candidate_id` 完全一致；
  - 正式流程链接必须为空。
- 正式流程行拒绝候选处置及候选前缀正式 ID。
- 补充正式/候选互斥、错误处置、候选不匹配及伪官方身份反例。

## Artifacts And Evidence

修改路径：

- `app/domain/contracts/protocol_controls.py`
- `app/domain/contracts/protocol_control_matrix.py`
- `tests/v2/protocols/test_protocol_control_matrix.py`
- `tests/v2/protocols/test_slice58a_full_protocol_coverage_contracts.py`

兼容性：

- 矩阵合同继续使用 `phase5/control-matrix/v2`。
- `ProtocolSectionCoverageManifest` 保持 `phase5/v1`；新增字段为可选，旧正式流程清单仍有效。
- D001 后续迁移时，未发布正式流程目录的候选流程单元需填写 `linked_procedure_candidate_id`，正式流程单元继续填写 `linked_procedure_catalog_item_id`，不得混填。

## Commands And Observations

运行：

```text
.venv/bin/pytest -q \
  tests/v2/protocols/test_protocol_control_matrix.py \
  tests/v2/protocols/test_slice58a_full_protocol_coverage_contracts.py \
  tests/v2/protocols/test_slice58b_control_planning.py \
  tests/v2/protocols/test_slice58c2_phase_applicability_agent.py \
  tests/v2/protocols/test_slice58c_control_deconstructor.py \
  tests/v2/protocols/test_slice58c_protocol_control_gate.py \
  tests/v2/protocols/test_contract_schema.py
```

结果：`129 passed`

## Blockers Or Missing Environment

无功能阻断。`.venv/bin/ruff` 不可用，因此未执行 Ruff。

## Rerun Requests Or Next Step

请父 Codex 使用真实 D001 冻结清单验证候选流程单元字段迁移，并进行最终临床语义与工件验收。
