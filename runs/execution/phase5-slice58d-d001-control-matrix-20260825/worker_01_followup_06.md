# Execution Output: phase5-slice58d-d001-control-matrix-20260825 - worker_01

## Boundary And Context Check

- 未读取或修改 D001 工件。
- 仅修改矩阵合同、矩阵校验器及矩阵测试路径。
- 未扩大生产或其他源文件范围。

## Work Performed

- 矩阵合同升级至 `phase5/control-matrix/v4`。
- `MatrixReviewNode` 新增可选 `workflow_basis_row_id`：
  - `source_anchor_ids` 可为空；
  - 节点必须至少具备直接来源或流程依据之一；
  - 直接来源若存在，仍强制唯一、字典序及行内来源闭包。
- 增加矩阵级流程依据校验：
  - 依据行必须存在于同一矩阵；
  - 必须是 `REQUIRED_PROCEDURE`；
  - 不得引用自身、官方行或其他章节控制行；
  - 流程行必须包含相同 `review_stage`，且其直接来源锚点支持该阶段。
- 官方行可在自身条款未命名筛选/基线时引用流程审核行；流程锚点不会并入官方行 `source_anchors`。
- Markdown 增加中文节点依据，例如：
  - `节点依据：研究流程中的流程必做 01（控制短标题）`
- JSON 与隐藏行注释保存节点依据身份、节点顺序及直接锚点；可见正文不显示稳定 ID。
- 校验器升级至 `phase5/control-matrix-validator/v4`。

## Artifacts And Evidence

修改路径：

- `app/domain/contracts/protocol_control_matrix.py`
- `app/protocols/protocol_control_matrix.py`
- `tests/v2/protocols/test_protocol_control_matrix.py`

新增测试覆盖：

- 官方行仅通过流程依据获得审核阶段支持；
- 同时存在直接来源和流程依据；
- 未知依据行；
- 引用自身；
- 引用非流程行；
- 流程行缺少相同阶段；
- 无任何节点依据；
- Markdown 隐藏依据身份篡改；
- 可见 Markdown 不泄露流程依据内部字段或行 ID。

## Commands And Observations

矩阵聚焦测试：

```text
49 passed in 0.10s
```

矩阵及 5.8a-c/合同回归：

```text
160 passed in 0.74s
```

语法编译检查：

```bash
.venv/bin/python -m py_compile \
  app/domain/contracts/protocol_control_matrix.py \
  app/protocols/protocol_control_matrix.py \
  tests/v2/protocols/test_protocol_control_matrix.py
```

结果：通过，无输出。

## Blockers Or Missing Environment

- 未读取真实 D001，故未执行 D001 工件迁移或临床语义验收。
- v3 节点 JSON 若仍只有空 `source_anchor_ids`，需补充合法 `workflow_basis_row_id`；已有直接来源节点无需迁移。
- 父 Codex 仍需负责真实方案来源及最终临床/可见工件验收。

## Rerun Requests Or Next Step

迁移旧矩阵时：

- 直接来源节点：保留 `source_anchor_ids`；
- 流程表支持节点：设置 `workflow_basis_row_id`，并确保同矩阵流程行的节点阶段及来源锚点满足 v4 校验；
- 不得将流程来源锚点复制进官方规则行的 `source_anchors`。
