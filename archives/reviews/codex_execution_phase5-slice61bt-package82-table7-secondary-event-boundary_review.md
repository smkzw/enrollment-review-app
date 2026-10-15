# Codex Execution Review: phase5-slice61bt-package82-table7-secondary-event-boundary

## Verdict

**Accept after parent revision.** 第 82 包表 7 模型外来源闭包可接受；不接受把示例细节提升为整行必要条件、把表 7 的“严重”自动等同于 SAE、或用相邻记录规范反推表 7 未写明逻辑。

## Worker Outputs

- `worker_01` 核对原始 DOCX、结构块、覆盖清单和冻结计划，确认表题 `body.p1032` 绑定 `body.t12`，第 82 包只拥有 `body.t12.r0-r4`；并识别冻结上下文缺少 `p1030/p1031/p1033`、却含无关 `body.t7.r0` 的来源选择缺陷。
- `worker_02` 建立配置、父级清单、模型外准备和专项回归。初稿把无关的Ⅲ期疗效表 `body.t7.r0/body.p507` 作为防混同材料加入提示，并把 r1 示例中的“无需额外治疗”提升为额外通用条件。
- `worker_03` 提供条件反转、行列错配、t7/t12 混同和跨包吞并反例；其关于表格 5×4 几何、r2/r3 多段示例及 r4 关联不确定边界的挑战有效。其“表中严重必然沿用 SAE 定义”的表述缺少显式交叉引用，未采纳。

## Manager Assessment

父级修订采用最小提示原则：移除无关 `body.t7.r0/body.p507`，只凭 `p1032` 表题、相邻结构和 `body.t12` 原文绑定表 7；保留 `p1030-p1032`、`p1033-p1042` 及必要的 AE/TEAE/SAE 和记录规范为只读语境。所有权与候选发射权不变。

表 7 四行按“类型列、示例列、结果列”分别保真。r1 示例中的“无需额外治疗”不再被提升为整行新增合取条件；r2 示例病种不升格为通用门槛；r3 保留“时间上分离”与“具有重要医学意义”的合取；r4 的“无法确定”只指事件关联不清楚，不得改写为证据不足或入排待补证。

进一步收紧相邻语义关系：`p996/p997` 仅提供 SAE 定义语境，表 7 未明示交叉引用时不得把 r2 的“严重”自动等同于 SAE；`p1024/p1026` 分别是全量记录义务和单一事件项术语规范，不得反推表 7 的拆分、合并或条件分支。

## Codex Independent Verification

1. 模型外准备：`5 owned / 23 attached / 28 total`，提示 `42315` 字符，SHA-256 `4f9e69ef8acae49aebf0baab4884414c7e68476f0bc7b65815b68be2c9733696`，`claims_complete=false`。
2. 配置 SHA-256：`2799c96f742d0a89281452ffd8919e66d5e8291526294235b6f5d2ed547b0f54`。
3. 第 82 包专项：`37 passed, 5 warnings`；Phase 闭包：`325 passed, 5 warnings`。
4. 方案与 Agent 全量：`1198 passed, 58 warnings`；治理工具：`30 passed`。
5. `jq empty`、提示最小性检查、生成缓存清理和 `audit-execution` 通过；执行审计无警告或错误。
6. 未调用临床语义模型、未发布、未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Cleanup Decision

保留受控执行提示、报告、日志、父级修订后的配置和模型外准备证据，以便追溯两类被拒绝路径：无关反例反向注入提示，以及相邻术语/规范被错误提升为逻辑前提。仅清理本轮生成的 Python 缓存，不删除验收证据。
