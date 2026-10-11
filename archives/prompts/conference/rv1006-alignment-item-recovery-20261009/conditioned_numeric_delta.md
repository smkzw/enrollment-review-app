# 同会话有界续审

延续原只读工程权限与报告边界，不执行测试、不读取.env、DB、病例或临床原答，不写源文件。报告由runner保存。不重读全部历史，最多6次聚焦读取。

基线现已提交931a50c0，上一审四项意见已修：空范围拒绝、阶段边界、数值只修四字段/失败回原稿、合法negative保留不晋级。现有真实作业只保留成功兄弟，原子回包因同一原文同时填写source_clause和source_clauses而结构拒绝；原答保留，没有采用。原文/数值不在本包中，以下只审通用源码与合成夹具。

本次差异仅两个通用边界：
1. `_merge_obligation_atom_repair(...numeric_predicate_only=True)`：若source_clauses精确等于[source_clause]，将重复source_clause改null，保留原始响应回执；不等价/多条/未知仍原合同拒绝，不改变原子来源、值、单位、兄弟或旧证明。提示明确互斥字段与原文单位，不将次数默改unitless。
2. `validate_candidate_alignment`：完整源句覆盖及每分支条件/义务先核，唯一数值比较可引用当前句内自己的比较片段，不强制重复条件前缀。片段须逐字在原句中，数字集合与比较方向集合相等，比较符/值/单位仍逐项验证。裸数字/错方向/错单位/缺条件/空分支仍拒。

读4个已知文件中的上述函数与新增`conditioned_numeric_consequence`、`equivalent_source_fields`/`different_source_fields`/numeric_gap反例。检查是否可借短比较摘录遗漏决定性量词/例外/条件，或重复来源归一化选择不同证据。只给实际反例与最小修复；没有新证据不建议重建框架、放松源保护、第三模型或重读方案。指出这次修订与上次审阅意见是否有冲突。新代码未生产采用，测试与clinical acceptance分别记录。
