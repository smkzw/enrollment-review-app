# Execution Output: phase5-slice58d-d001-control-matrix-20260825 - worker_01

## Boundary And Context Check

仅修改授权合同/矩阵测试路径；未读取或修改 D001 工件，未硬编码 D001 编号或项目文本。

## Work Performed

- 矩阵合同升级至 `phase5/control-matrix/v3`，校验器升级至 `phase5/control-matrix-validator/v3`。
- 增加顶层连接词、长列表、列表引导语和注记标签阻断；括号内示例逻辑不误拆。
- 复合 DNF 组强制提供 `logic_basis_zh` 与直接 `source_anchor_ids`，并明确“且/或”关系。
- 增加来源逻辑未表达阻断，防止 `unexpressed_logic=[]` 掩盖结构缺失。
- 扩展时间锚点检查：筛选/基线不得泛化为 `EVENT_DATE`，首次给药/随机不得使用筛选或泛化事件日期，窗口不得使用 `ON`，筛选与基线不得折叠为单锚点，半衰期择长窗口必须完整表达。
- 最低证据拒绝空泛事实类型和原文复述；官方入排行必须有来源类型；客观结果要求同期客观来源；专业判断要求研究者评估记录。
- `MatrixReviewNode` 增加必填 `source_anchor_ids`，并校验节点阶段/名称由直接来源支持。
- 补充模型层与严格校验层反例。

## Artifacts And Evidence

本轮修改：

- `app/domain/contracts/protocol_control_matrix.py`
- `app/protocols/protocol_control_matrix.py`
- `tests/v2/protocols/test_protocol_control_matrix.py`
- `tests/v2/protocols/test_slice58a_full_protocol_coverage_contracts.py`

迁移要求：

- 所有矩阵节点 JSON 需新增并填写 `source_anchor_ids`。
- 复合 DNF 组需补 `logic_basis_zh` 和直接来源锚点。
- 官方最低证据需补非空 `required_source_types`。
- 涉及客观结果或研究者判断的行需设置相应证据标志。
- 旧 v2 JSON 需按上述字段迁移后才能通过 v3 校验。

## Commands And Observations

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

结果：`154 passed`

版本核对：

```text
phase5/control-matrix/v3
phase5/control-matrix-validator/v3
```

## Blockers Or Missing Environment

无功能阻断。系统未提供 `python` 命令，但 `.venv` 测试与导入核对均正常。

## Rerun Requests Or Next Step

请父 Codex 对真实 D001 58 行矩阵执行只读语义抽查，重点确认 DNF 拆分、时间锚点命名、最低证据对象和节点来源绑定。 lexical 规则无法自动判定所有不可分割术语或临床语义例外，未知情况应继续由父 Codex 人工验收。
