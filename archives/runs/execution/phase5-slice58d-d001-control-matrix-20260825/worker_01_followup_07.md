# Execution Output: phase5-slice58d-d001-control-matrix-20260825 - worker_01

## Boundary And Context Check

- 未读取或修改 D001 工件。
- 仅修改 Worker 01 矩阵合同、校验器及矩阵测试路径。
- 未扩大生产或其他源文件范围。

## Work Performed

矩阵合同与校验器升级至 v5：

- `CONTROL_MATRIX_CONTRACT_VERSION = phase5/control-matrix/v5`
- `CONTROL_MATRIX_VALIDATOR_VERSION = phase5/control-matrix-validator/v5`

新增通用例外树能力：

- `stable_protocol_control_matrix_trigger_branch_id()` 按矩阵行身份和触发 DNF 稳定序位派生触发分支身份。
- `MatrixDnfGroup.trigger_branch_id` 保存触发分支稳定身份，并在模型及严格校验中强制派生闭合。
- `MatrixDnfGroup.waives_trigger_branch_ids` 为每个例外路径声明可豁免的触发分支集合。
- `MatrixDnfGroup.negated_atom_ids` 结构化表达 NOT；正向原子与 NOT 原子不得重复。
- DNF 继续表达：
  - 组内 ALL；
  - 组间 ANY；
  - `negated_atom_ids` 的 NOT。
- 例外严格拒绝：
  - 无触发表达式；
  - 缺失作用域；
  - 未知触发分支；
  - 适用/义务层身份；
  - 例外来源锚点缺失或越界；
  - 未经来源明确支持而作用于全部触发分支。
- 中文 Markdown 显示例外适用的触发条件中文表述，不显示 `pcm-trg-*`、分支字段名或其他机器身份。
- JSON 与隐藏行注释保存触发分支、NOT 原子和例外作用域，并参与序列化一致性校验。
- v4 JSON 不会按 v5 等价接受。

## Artifacts And Evidence

本轮修改：

- `app/domain/contracts/protocol_control_matrix.py`
- `app/protocols/protocol_control_matrix.py`
- `tests/v2/protocols/test_protocol_control_matrix.py`

新增回归覆盖：

- 例外路径 A 仅作用于触发分支 A；
- 多个例外路径作用于同一触发分支；
- 不同例外路径作用于不同触发分支；
- 缺失、未知、适用/义务层及未经来源支持的全触发分支作用域；
- 触发分支稳定身份篡改；
- 触发及例外表达式中的 NOT；
- JSON/Markdown 隐藏身份一致性；
- 中文可见层不泄露分支 ID/内部字段；
- v4 schema 不被 v5 接受。

## Commands And Observations

矩阵聚焦测试：

```bash
.venv/bin/pytest -q tests/v2/protocols/test_protocol_control_matrix.py --tb=short
```

结果：

```text
58 passed in 0.09s
```

矩阵及 5.8a-c/合同回归：

```bash
.venv/bin/pytest -q \
  tests/v2/protocols/test_protocol_control_matrix.py \
  tests/v2/protocols/test_slice58a_full_protocol_coverage_contracts.py \
  tests/v2/protocols/test_slice58b_control_planning.py \
  tests/v2/protocols/test_slice58c2_phase_applicability_agent.py \
  tests/v2/protocols/test_slice58c_control_deconstructor.py \
  tests/v2/protocols/test_slice58c_protocol_control_gate.py \
  tests/v2/protocols/test_contract_schema.py \
  --tb=short
```

结果：

```text
169 passed in 0.62s
```

语法编译检查：

```bash
.venv/bin/python -m py_compile \
  app/domain/contracts/protocol_control_matrix.py \
  app/protocols/protocol_control_matrix.py \
  tests/v2/protocols/test_protocol_control_matrix.py
```

结果：通过。

## Blockers Or Missing Environment

- 未执行真实 D001 工件迁移或验收，符合 Worker 01 边界。
- 通用校验能确定性保证分支身份、作用域闭合、来源锚点和 ALL/ANY/NOT 结构，但不能仅凭字符串判断例外原文是否在临床语义上确实对应某一触发分支。
- “全部触发分支”目前要求来源摘录出现明确的全称范围词；更复杂的自然语言范围仍需人工语义审阅。

## Rerun Requests Or Next Step

Worker 02 的下一步：

1. 将其真实矩阵生产/水合输入迁移到 v5；
2. 为每个触发 DNF 分支按稳定顺序生成 `trigger_branch_id`；
3. 将每条例外路径拆成独立 DNF 组，填写 `waives_trigger_branch_ids`、来源锚点及必要的 `negated_atom_ids`；
4. 运行严格矩阵校验，逐项确认例外不会跨越未授权触发分支；
5. 对无法确定作用域的来源保持阻断并回报，不得使用全触发分支兜底。
