# Codex Conference Review: phase5-slice58-cross-section-controls-20260824

Date: 2026-08-24

## Verdict

**REVISE 并纳入 Slice 5.8a-5.8e。** 两名参与者对当前两目录输入边界的核心阻断判断正确；其数据模型建议只选择性采纳。

## Boundary Compliance

- 两个参与者均为只读会商，未写产品文件，未代替独立测试者。
- Pi 角色使用当时实时路线 `muse-spark-1.2-contributor:xhigh`；Cursor 角色使用 `cursor/auto`，均无 fallback。
- 临床真实文件由 Codex 主会场定向只读审计，会商参与者没有越界读取。

## Participant Outputs Reviewed

- 一致正确：流程表必做项不等于全部入排控制；需要第三类一等来源与精确覆盖门禁。
- 一致正确：不能扩容 `required_procedures`，不能制造新 IN/EX，不能用文本相似度静默合并重复/补充/冲突来源。
- 采纳：冻结候选身份后由 Agent 结构化，确定性门禁负责来源闭包、时间锚点、期别、逻辑和冲突。
- 不采纳：为用户可见控制制造 `CTRL-xx` 伪官方编号。
- 不采纳：将单个控制限制为 `do | condition | prohibition` 三选一；真实控制可包含多个必须同时成立的义务原子。
- 不采纳：仅使用节标题允许列表或关键词作为完整性证据。这只能排优先级，不能证明未命中单元不含控制。

## Conference Panel Review

- 正式设计为“全文结构单元覆盖清单 -> 冻结候选 -> Agent 结构化/明确排除 -> 跨章节对齐 -> 正式方案控制目录 -> 原子发布”。
- 审核节点绑定新增“提前关注/本节点判定/后续节点复核”，避免将基线/随机前洗脱限制在筛选期直接判死，同时不丢失前瞻风险提示。
- 不完整、时间锚点未解、期别未解、来源越界或冲突未解均阻断整份规则模型发布。

## Main-Venue Codex Review

TODO

## Codex Independent Verification

- 源码审计确认 `CatalogKind`、`FrozenProtocolCatalog`、`ProtocolDeconstructionInput` 及 assembler 当前只接受两份目录。
- 源码审计确认 `build_required_procedure_catalog()` 只处理流程矩阵表，不会读取 D001 表 5。
- Codex 从真实 D001 II 方案逐行读取表 5，确认 12 条禁限用药/治疗时间窗、半衰期分支及来氟米特洗脱例外，且当前 r6 输入不含这些来源。
- 新增结构门禁曾与 provider Schema 的无 `anyOf/allOf/oneOf` 约束冲突；已改为 Schema 保持稳定平铺形状，确定性水合拒绝三类原子均为空的 group。聚焦回归 `31 passed`。

## Final Decision

采纳修订后的全方案控制路线，将其记入总设计、分阶段计划和 Trellis Slice 5.8a-5.8e。下一步先做合同与全文覆盖构建器，不直接启动完整 D001/MG 和三路独立测试者。
