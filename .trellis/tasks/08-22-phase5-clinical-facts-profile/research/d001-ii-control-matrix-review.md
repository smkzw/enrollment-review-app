# D001 II期全方案控制对照矩阵验收报告（Worker 03）

- 方案：D001-02-002:v1.0；选定期别：II期。
- 源文件 SHA-256：362443131f0d384c82c80f6a37396084f7d3301b51162201749c0488b0f2dd98。
- 合同：phase5/control-matrix/v5；快照：worker02-d001-final-structure-snapshot；全文清单：coverage-manifest-d001-ii-362443131f0d384c。
- 结论：claims_complete=false。已生成 24 条其他章节候选；严格全文来源闭包仍被阻断。

## 1. 边界与既有身份

本次只新增其他章节候选控制，不修改既有 36 条官方父规则、22 条流程身份、触发分支身份、例外作用域或官方来源摘录。
合并矩阵共 82 行：既有 58 行 + 本次 24 条其他章节候选。
独立其他章节工件含 1 条已接受的入排标准审核流程依据行，仅用于关闭候选审核节点的矩阵内流程依据，不计入新增候选数量。

## 2. 全文控制核对与关系处置

| 控制主题 | 来源范围 | 关系处置 | 结果 |
|---|---|---|---|
| 合并用药/治疗 | body.p749、body.p837、body.p751–p755 | 补充流程合并治疗行；不重复建立流程身份 | 已纳入 |
| 洗脱/禁限用药治疗 | body.t10.r1–r12 | 12 个表5行分别保留；分别补充 EX-18/19/10/25/26 | 已纳入 |
| 重复检查/重新筛选 | body.p703、body.p868 | 补充流程入排审核；保留一次复查、一次重新筛选和 D1 前基线窗口 | 已纳入 |
| 结果有效期/复测 | body.p797、p804–p805、p813 | CT、病毒学、结核复测分别处置 | 已纳入 |
| 结核/感染 | body.p807–p813 | 补充 EX-09/流程 TB；随机门控、治疗时长、禁用药物和复测均保留 | 已纳入 |
| 妊娠/避孕 | body.p327、p815–p816、p1325–p1326 | 补充 EX-29、IN-06 和流程 FSH；II 期第12周与首次给药前阳性门控保留 | 已纳入 |
| 随机/首次给药前 | body.p333、p364、p528、p878–p885 | 补充入排复核、D1 时点、随机资格、安全记录和基线材料 | 已纳入 |
| 日记卡/依从性 | body.p337–p338、p743、p746 | 首次给药后的治疗执行要求不并入入排矩阵；D1 前评分/基线完整性另行纳入 | 已处置为不污染入排 |
| II/III 补救治疗 | body.p761–p763 | 仅作期别边界，不将 III 期治疗后要求投影为 II 期入排控制 | 已处置为期别边界 |

关系计数：{"supplementary_requirement":27,"further_explanation":4}。未发现需要改写既有身份的实质冲突；未将重复表述静默合并。

## 3. 确定性校验与来源闭包

- 候选矩阵模型构造：通过。
- 合并矩阵行身份、候选身份、来源锚点身份、义务 DNF、时间锚点、审核节点和最低证据结构校验：通过。
- JSON/Markdown 同身份序列化校验：生成脚本通过；渲染 Markdown 未作为本次三件授权写入之外的文件写入。
- 严格全文闭包：阻断。当前可读上下文只有 Worker 02 已接受矩阵 JSON 与 checkpoint；没有可供新候选逐条闭合的冻结 ProtocolSectionCoverageManifest。
- 新候选 structure_unit_id 使用确定性 pending 身份 su-cross-*，不能冒充 Worker 02 已接受结构单元身份。
- checkpoint 记录全文母集 1,689 个结构单元，其中 1,433 个期别语义仍为 ambiguous、分 235 批；不能声明全量 II 期闭包，也不能声明 claims_complete=true。

## 4. 实际阻断

1. SOURCE_MANIFEST_REQUIRED / SOURCE_UNIT_UNKNOWN：缺少冻结全文清单工件，无法证明新锚点的 structure_unit_id、source_ref、heading、span 完全属于接受清单。
2. PHASE_UNRESOLVED 风险：1,433 个 ambiguous 单元未完成全量 II 期投影。
3. 因上述阻断，合并矩阵与其他章节矩阵均保持 claims_complete=false；没有为了产生非空报告而放行。

## 5. 源覆盖参考

本轮新候选使用 42 个去重 source_ref：

- body.p1325
- body.p1326
- body.p327
- body.p333
- body.p364
- body.p528
- body.p703
- body.p749
- body.p751
- body.p752
- body.p753
- body.p754
- body.p755
- body.p797
- body.p804
- body.p805
- body.p807
- body.p808
- body.p809
- body.p811
- body.p812
- body.p813
- body.p815
- body.p816
- body.p837
- body.p868
- body.p878
- body.p879
- body.p880
- body.p885
- body.t10.r1
- body.t10.r10
- body.t10.r11
- body.t10.r12
- body.t10.r2
- body.t10.r3
- body.t10.r4
- body.t10.r5
- body.t10.r6
- body.t10.r7
- body.t10.r8
- body.t10.r9

## 6. 下一步

将 d001-ii-cross-section-controls.json 与 d001-ii-control-matrix.json 绑定 Worker 01 v5 冻结全文清单，逐个把 su-cross-* 替换为真实 structure_unit_id，并运行严格闭包、期别、时间、节点、逻辑、例外作用域和重复关系校验。只有全文清单每个单元均有来源可审计处置且严格闭包通过，才允许父级更新 claims_complete。

