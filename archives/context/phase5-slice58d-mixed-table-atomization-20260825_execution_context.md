# Phase 5.8d 混合期别表格原子化执行上下文

## 目标

修复全文覆盖清单将同一表格行内分别属于 II 期和 III 期的单元格压成一个不可判定结构单元的问题，使单期项目能够逐来源成员排除对侧期别内容，而不是把“同时出现两个期别”误判为跨期共同要求。

## 真实失败证据

- D001 II 修复后清单为 1,689 单元、1,284 模糊单元、217 批。
- 真实本地模型对 package ordinal 32 的技术 gate 最终通过，但把方案概要表中分别列出 II/III 期目的、终点和设计的混合表格行全部判为 `cross_phase_shared`。
- 该批经历两次 schema 修复，耗时 1,331.98 秒；最终 12 单元、6 组、12,433 字符。技术可解析不代表医学语义正确。
- 根因位于 `build_full_protocol_coverage_manifest`：每一表格行无条件聚合所有非空单元格/段落为一个 `ProtocolStructureUnit`；四类期别处置无法表达同一行成员分别属于 selected/opposite/shared。

## 临床与结构边界

- “一行出现 II 期和 III 期”不是“该行内容跨期共用”。仅有明确共同适用语义才可 shared。
- 对阶段范围一致且无冲突的普通表格行继续保持完整行单元，避免无必要拆碎。
- 当行成员具有互斥明确期别、MIXED/UNKNOWN 组合或跨期比较时，必须按最小可回源成员边界原子化；每个原始非空 cell paragraph 必须且只能被一个覆盖单元拥有。
- 原子单元保留同一表根、行列、表题、行表头、列表头、成员路径、source span 和原文顺序；不能丢失表格上下文。
- 表头/共享标签若自身范围 UNKNOWN，不能因邻近 II/III 单元格自动默认共享；继续进入语义处置。
- 不硬编码 D001 表号、行号、期别内容或结构身份。

## 允许修改

- `app/protocols/full_protocol_coverage.py`
- `app/protocols/phase_applicability_planning.py`（仅确有必要）
- `app/domain/contracts/protocol_controls.py`（仅确有必要）
- `tests/v2/protocols/test_slice58a_full_protocol_coverage_contracts.py`
- `tests/v2/protocols/test_slice58c2_phase_applicability_agent.py`
- `tests/v2/protocols/test_protocol_control_matrix.py`（仅相邻身份断言需要）
- 当前执行记录、Trellis 研究和检查点。

## 完成证据

1. 合成表证明：同一行 selected/opposite 成员被分别原子化；普通同范围行仍聚合；每个 source_ref/span 恰好拥有一次。
2. 原子单元的表题、行表头、列表头、嵌套表路径和原文顺序完整。
3. D001 重建后，原 package 32 的 II/III 混合行不再作为整行 unknown 目标；selected/opposite 单元确定性处置，未知标签诚实保留。
4. 相关 gate、矩阵和协议回归通过；源 DOCX 哈希不变。

