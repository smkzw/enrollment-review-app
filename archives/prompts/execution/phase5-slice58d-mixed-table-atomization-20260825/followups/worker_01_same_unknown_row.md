继续同一执行会话，修正 Codex 独立复核发现的过度原子化。

当前 `_table_row_requires_atomization` 因任一成员为 UNKNOWN 就拆分整行，导致 D001 单元从 1,689 暴增到 2,403。该行为超出执行上下文：同一行所有成员均为相同单一 UNKNOWN 时，它们并不存在成员间适用范围冲突，仍可作为一行交给语义 Agent；逐 cell 拆分只增加输出与失去整行语义。

请实施最小通用修复：

1. 仅在成员 phase signature 不同、任一成员自身含多种/混合 scope、成员缺图、或显式 `cross_phase_comparison` 时原子化。
2. 全部成员均为 `(UNKNOWN,)` 时保持整行聚合；全部均为同一明确 scope 也保持聚合。
3. UNKNOWN 与 PHASE_II/III/SHARED 混在同一行时因 signature 不同而原子化；`(UNKNOWN, PHASE_II)` 等单成员复合范围也原子化。
4. 更新/增加测试证明上述边界及 source_ref/span 唯一所有权。
5. 运行聚焦回归并返回完整报告；不要运行真实 Agent 或修改源 DOCX。
