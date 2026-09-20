# Worker 01 同会话返修：补齐冻结清单的流程候选处置

Worker 02 已用真实 D001 证实 v2 合同仍存在不可表达状态：`StructureUnitDisposition` 的 `REQUIRED_PROCEDURE` 强制正式 `linked_procedure_catalog_item_id`，而矩阵 v2 正确禁止把候选身份写入正式链接。请在同一会话修复此根因。

本轮在原五个路径基础上额外授权：

- `app/domain/contracts/protocol_controls.py`
- `tests/v2/protocols/test_slice58a_full_protocol_coverage_contracts.py`

不要修改 D001 工件。

## 合同要求

1. 在冻结全文清单的 `StructureUnitDisposition` 增加明确的流程候选身份字段（例如 `linked_procedure_candidate_id`）。它是人工盲前/目录尚未发布时的来源候选，不是正式 `required_procedure_catalog_item_id`。
2. `REQUIRED_PROCEDURE` 处置必须且只能绑定正式流程目录身份或流程候选身份之一；两者互斥。其他处置不得携带任一流程身份。
3. 候选身份必须使用稳定、明确的候选前缀并拒绝 IN/EX/REQ/CTRL 伪官方形态；与矩阵 `source_candidate_id` 的身份格式兼容。
4. 矩阵候选流程行的严格校验必须要求每个来源单元：处置为 `REQUIRED_PROCEDURE`、`linked_procedure_candidate_id` 与行候选身份完全一致、正式流程链接为空。删除当前“合同无法表达所以必然阻断”的逻辑。
5. 正式流程行仍必须与 `linked_procedure_catalog_item_id` 完全闭合；不得把候选字段视为正式目录。
6. `claims_complete=true` 仍拒绝任何候选行，并仍要求非空正式权威目录。
7. 这不是扩展 Agent provider 草稿输出：除非现有发布/水合链确实需要，否则不要改 `ProtocolControlUnitDispositionDraft/Hydrated` 的语义。当前目标是让冻结人工验收清单可无损表示“已判定为流程控制，但正式目录尚未发布”。
8. 补充模型及严格校验反例：正式+候选同时存在、候选用于错误处置、候选不匹配、正式行引用候选处置、候选行引用正式处置均拒绝。
9. 运行矩阵聚焦、5.8a 全文覆盖合同及相关 5.8b-c 回归。

完成后报告合同兼容性、测试结果和 D001 迁移所需字段。
