v2 已完成：所有 33 个测试均已通过，且仅修改了两个授权文件。最终报告：

# 执行输出：medication-component-isolated-20260909 (续) - worker_01

## 边界与上下文检查

- 路径未变 (zcode / GLM-5.3-Flash, 允许的最大思考深度, off_peak 会话)。无模型/网络/临床/配置访问权限；未触碰所有者的运行器。
- 编辑前重新读取了这两个文件，以获取所有者的添加内容。**保留了所有者的两个测试：** `test_missing_batch_observation_is_not_silently_dropped`（由 `validate_extraction_batch` 中 `seen != set(by_id)` 的遗漏检查支持）以及 `test_adjacent_drug_substring_is_only_bound_not_clinically_accepted`（相邻药物引用 `药乙200mg` 绑定成功，但 `source_qc_required=True`/`product_acceptance=False`；添加了一个断言，即绑定成功并非归属证明）。
- v1 版本保持冻结状态：未编辑任何存档；工作模块在原位升级为 `medication-component/v2`。`git status` 显示确切只有这两个授权文件是新的/已更改的；测试运行仅针对新文件。

## 已执行工作 — 模块 v2 中的 API 变更 (`scripts/medication_component_experiment.py`)

1. **读取者身份：** `MedicationObservation` 现在需要 `lane: Literal["main-A","main-B"]` 和 `page_review_id`；两者均带入 `BoundComponentExtraction`。`compare_component_outputs` 会拒绝相同页面、**相同通道 (same lane)** 以及**相同 page_review_id**（按此顺序）——独立性仅来自通道+记录，绝非来自观察 ID。
2. **药物名称完整性：** `MedicationDrugNameComponent(MedicationComponent)` 具有强制的 `completeness: complete|fragment|uncertain|absent`；`null` 值要求为 `absent`，而非 `null` 值则禁止 `absent`。比较：两侧均为 `complete` 且文本相等 → `agree`；两侧 `fragment`/`uncertain` 文本相等 → **`unresolved`，绝不 `agree`**；一侧 `complete` 而另一侧非 `complete` → `unresolved`；文本不同 → `conflict`。无别名，无项目映射。
3. **时间列表 + 新组件：** `times: list[MedicationTimeComponent]`（必需；缺失时间 = 空列表；`null` 值项目被拒绝）。每项均有强制的 `role`（与 v1 相同的五种角色）和 `precision: day|month|year|partial|unclear`；值保持精确的原始子串（部分日期绝不会被丢弃）。添加了必需的 `ongoing` 和 `administration_count` 组件（均为可空值/引用），与管理频率分开。确定性保护：任何包含 `至`/`~`/`～` 的项目引用都会被拒绝，并提示必须将时间间隔拆分为 `use_start`+`use_end`（这是一个部分标记保护，已记录；选择更窄的引用仍然是模型的工作）。
4. **时间比较：** 项目按角色分组（排序），保留多重性；在角色内，多集 `(normalized value, unit, precision)` 不匹配 → `conflict`；缺失侧 → `missing`；相等 + 角色 `unclear` → **`unresolved`**；相等则为 `agree`。`use_start`/`use_end` 交换在两个角色上保持 `conflict` — 排序永远无法跨角色创建 `agree`。标量组件比较未变（基于元组的单位感知规范化）；总体仍为 `product_acceptance=false`，`source_qc_required=true`。
5. **提示词 v2：** 紧凑的中文；发送带有枚举交替的 JSON 实例形状 (`INSTANCE_SHAPE`)，而不是庞大的 `$defs` 模式；明确禁止输出 `$defs`/`properties`/`schema`。新说明：逐字复制包括剂型在内的药物名称，若不完整则使用 `fragment`（绝不猜测）；将明确的时间间隔拆分为两个项目；`unclear` 保持有效，带日期的使用说明不得自动变为 `use_start`；单次给药次数归入 `administration_count`，而非频率。仅使用 `…` 占位符 — 提示词中不包含真实药物的示例或黄金标准（测试断言 `阿司匹林` 不存在）。
6. **测试：** 33 个测试，仅限合成数据。新增：片段与片段匹配 → `unresolved`；`complete` 与 `fragment` → `unresolved`；部分日期逐字保留 + `precision` 差异 → `conflict`；匹配开始/结束 `agree` 对比交换 `conflict`；间隔引用被拒绝；`unclear`-与-`unclear` → `unresolved`；计数与频率分离；拒绝相同通道/相同记录；提示词形状/禁止/无真实数据断言。保留所有 v1 保证（源绑定、外来/上下文引用、释义、必需键、额外字段、空格与单位、逐字保留输入、从不接受、批处理版本字面量）。

## 工件、命令与观察

- 文件：`scripts/medication_component_experiment.py`，`tests/v2/scripts/test_medication_component_experiment.py` — 无其他。
- `.venv/bin/pytest tests/v2/scripts/test_medication_component_experiment.py -q` → **33 个通过**（最终运行）。迭代修复均为测试固件错误（配对观察之间不匹配的提取/观察 ID；在 b 侧提取中引用了其配对观察中不存在的 `qd`/`100mg`/`口服` 文本）— 验证器捕获了每一个，这证实了绑定和身份检查是有效的。模块在测试期间无需更改。
- 语义变更值得注意：与 v1（角色不匹配 → 一个 `conflict` 行）不同，v2 按角色分组时间，因此角色差异显示为两个明确的 `missing` 行，并且永远无法 `agree`。

## 障碍或缺失环境

无。

## 局限性（如实说明；无产品或临床验收声明）

- **`completeness` 是模型声明，而非验证事实。** 药物名称上的 `agree` 仅意味着两侧都*声明*了完整且相等的源文本；它不提供任何医学正确性或所有权保证，且 `source_qc_required` 仍保持 `true`。
- **子串绑定 ≠ 归属权。** 摘录内相邻药物文本仍需要人工源 QC（所有者的相邻药物测试固定了这一点）。
- `_INTERVAL_MARKS` 保护仅捕获引用中明确的 `至`/`~`/`～` 标记；拆分时间间隔主要依靠提示词指令 + 审查，而 `precision`/`role`/`ongoing`/`count` 的分类是仅受确定性一致性比较约束的模型声明。
- `unclear`-角色匹配会产生 `unresolved`（而不是 `agree`），设计上没有状态会升级为已接受；所有输出仍为 `product_acceptance=false` 且 `source_qc_required=true`，比较保持纯文本/规范化（无语义模型）。
