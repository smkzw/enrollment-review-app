Continuing read-only verification pass. Reading the 8 declared windows (prioritizing the F1 failure-marker/replay path and the F6 bounded-context metadata path; I'll declare which windows the 8-read cap forces me to leave unread).

# Conference Output: rv1006-restricted-registration-context-review-20261008 - evidence_single_object

## Output

### 0. 复核结论（先给裁定）

| 项 | 裁定 | 依据类型 |
|---|---|---|
| **F1 已修** | **成立**：失败登记现在是*持久、带标记、双 stage 标签下都被拒绝重放*的 `deep_failure_diagnostic/v3`；成功检查点仍为 `deep` 且**在构造上不可能**携带失败标记 | 源码 + 新测试断言（确定性） |
| **F6 已修** | **成立**：宿主选定相邻范围、`stop_reason`、`complete_list_asserted: Literal[False]`，契约层逐项校验同格连续、禁止外部/非相邻引用，两类提示词都明示“有界片段、不证明清单完整、不得把截断当结尾” | 源码 + 契约 + 新测试（确定性） |
| **F2** | 接受“同行/前置行放行是日程表头有意设计”；**新续读已严格同格**（构建器与契约双点强制） | 确定性 |
| **F3/F4** | 接受为*本窗口内*的边界取舍，记录残余为“登记回执强度受发布层二次校验兜底”，**不要求**扩展为全局引用架构 | 接受 + 残余 |
| **F5** | 接受放弃（属临床/产品判断，非我权限）；仅记录一个可审计性单点 | 接受 |
| **F10** | 三项**全部落地**：fixture 坐标修正、字符/单元双预算覆盖、纯元数据单元格边界覆盖 | 确定性 |
| **是否存在新的具体首要缺陷** | **在本次新读窗口内：没有可达路径可证的新缺陷。** 唯一可能仍属首要缺陷的是 pass-1 HC-1 被收窄为*一个未读谓词*：`_replay_checkpoint` 的拒绝依据是“可删除的声明标记”还是“可派生的运行状态” | 条件性 / 需 1 次读 |

**读预算**：本轮 8/8 用完（4+4）。**未读（预算所限，非跳过）**：`app/services/protocol_control_execution.py:1147-1244`、`app/agents/protocol_control_deconstructor.py:322-385`、`app/agents/protocol_control_source_interpretation.py:2578-2608`。后者的价值在 §8 说明。

**我不认证任何测试通过数**（488 / 12 / 最终窗口）。我能读到的只是*断言内容*，不是执行结果；owner 的六响应零网络重放我按“所有者报告的诊断”对待，不作为模型调用、也不作为最终临床 QC。

---

### 1. F1 处置：逐项验证

`owner 固定：failed registration 是 durable deep_failure_diagnostic/v3，保留 actual source/review/attempts/private raw answers 与失败标记；即使 stage 被误标为 deep 也不能通过 completed replay；成功检查点仍为 deep 且无失败标记。`

| 子主张 | 代码证据 | 判定 |
|---|---|---|
| 失败标记 + schema v3 | `protocol_control_execution.py:3452` 新增 `failed: bool = False`；`:3455-3459` 条件展开写入 `schema_version="phase5/deep-failure-diagnostic/v3"`、`failure_reason_version`、`restricted_registration_failed: True` | 确定性成立 |
| stage 正确 | `:3460` `"stage": "deep_failure_diagnostic" if failed else "deep"` | 确定性成立 |
| 三条失败路径都带标记 | `:3510-3513`（`failed=True`：登记未产出）、`:3522-3525`（`ValueError` 再校验失败）、`:3532-3535`（再派生不一致）**全部**传 `failed=True`；成功返回 `:3537-3540` **不传** | 确定性成立；成功态**构造上不可能**带标记（条件展开为空） |
| 保留实际来源 | `:3455` 展开 `result.model_dump(mode="json")` → `source_interpretation`/`source_statement_coverage`/`source_target_review`/`attempts` 顶层可见；测试 `:667-668` 断言前两者与冻结值相等 | 成立（review/attempts 由构造保证；测试未显式断言 → §7 小补） |
| 保留来源处置 | `:3471` `restricted_batch`；测试 `:669` 断言等于**登记前**输出 `output` | 成立（不是登记后的新派生） |
| 保留实际原答（含畸形） | `:3469` `_deep_attempt_raw_outputs(result)`；测试 `:673-674` 断言 `raw_output_text == raw` 且 `role == "restricted_source_definition_consumer"`；失败矩阵含 `declaration_rejected`（`:631-632` 把原答设为 `"{"`）仍逐字保留 | 成立（**畸形原答也保留**，这是重要正向） |
| 原答私有化 | 测试 `:671` `final_output is None`；`:672` `status == "需要核对"`；`run_result` 走既有 `_deep_attempt_raw_outputs` 通道（pass-1 已证 `run_result` 内不含 `raw_output_text`，测试 `:596`） | 成立 |
| 失败态可被**授权读取器**还原 | `:4058-4068` `_saved_failed_deep_run_result`（按 `model_fields` 过滤、强制 `status/batch_id`）→ `:4047-4055` 校验尝试身份四元组与 `sha256/长度` 后才回填 `raw_output_text`；测试 `:675-677` 断言还原出的 `source_interpretation` 与原答 | 成立 |
| **不得通过 completed replay** | 测试 `:678-682`：`for stage in ("deep_failure_diagnostic","deep")`，`_replay_checkpoint(replace(context, last_checkpoint={**saved, "stage": stage}))` 两者均抛 `PROTOCOL_CONTROL_CHECKPOINT_INVALID` | **行为已验证**；**拒绝机制未读**（见 §8 Q1） |
| 输入不被污染 | 测试 `:683` `result.model_dump == frozen` | 成立 |
| 恢复不是自动成功 | `:3485-3486` 仅在 `source_definition_consumers is None` 时重新走一次**真实**登记：`:3494-3498` 调用 `declare_source_definition_consumers`，`:3503-3504` 取 `take_call_receipts()`；失败态 `retryable=False`（`:3507/3519/3530`，测试 `:662`） | 成立：恢复 = **新的真实登记 + 当前门再派生**，不是重放成功、不是医疗采用 |

**F1 残余（不是缺陷，但是本轮最值得收口的一点）**：失败态识别目前依赖**声明式标记**（`restricted_registration_failed` / `schema_version` / `stage`）。这三个键都是可删除的；而失败态在**派生意义上**同样可识别——`source_definition_consumers is None` 且 `restricted_source_definition_consumer_attempts` 非空（或 `attempts[-1].outcome != "parsed"`）。若 `_replay_checkpoint` 只按键判断，则“删除标记 + stage 改 deep”会退回到 pass-1 HC-1 的形状；若它同时看派生条件，则不受影响。测试证明它**不依赖 stage**，但没证明它不依赖可删除键。
**最小修复（2 行，非阻断）**：在拒绝谓词中并入派生条件 `saved.get("run_result",{}).get("source_definition_consumers") is None and saved.get("run_result",{}).get("restricted_source_definition_consumer_attempts")`（对顶层展开副本同理）。

**F1 第二个残余（低·卫生）**：失败检查点把运行结果存了**两份**——顶层展开（`:3455`）与嵌套 `"run_result"`（`:3468`）。今天两份内容相同，但 `_saved_failed_deep_run_result` 读**顶层**、常规读取器读**嵌套**；任一被编辑就会让两个读取器看到不同状态。
**最小修复**：`:3454-3472` 内先算一次 `run_view = result.model_dump(mode="json")`，两处共用；或在新测试加 1 行 `assert saved["run_result"] == {k: v for k, v in saved.items() if k in ProtocolControlAgentRunResult.model_fields}`。

---

### 2. F6 处置：逐项验证

`owner 固定：记录宿主选定的有界相邻来源 ID、停止原因与 complete_list_asserted=false；投射进 source/author 输入；保存进既有冻结批次；复用时可比较；空元数据不参与批次序列化以保持历史形状，只有受影响批次获得新 material identity。`

| 子主张 | 代码证据 | 判定 |
|---|---|---|
| 宿主选定范围 | `protocol_control_planning.py:1060-1077` 扫描严格条件链；`:1072` 记录 `included_ids`；`:1082-1086` 写入 `continuation_bounds[intro_id]` | 确定性成立 |
| 停止原因完备 | `:1062-1069` 四级边界（坐标→标题→单元格→字符）；`:1075-1077` `next_intro`；`:1078-1081` `for/else` 区分 `unit_limit` 与 `source_end`（判据 `position+1+len(included)<len(all_units)`）——**每个退出路径都赋一个原因**，无 None 泄漏 | 确定性成立 |
| 三字段冻结进契约 | `protocol_controls.py:2529-2535` `TableContextReadingBound`；`:2558-2560` 批次字段带 `exclude_if=lambda v: not v` | 成立 |
| 有界：单位上限 | 构建器 `:1061` 切片上限；契约 `:2628-2629` 镜像 `MAX_SOURCE_LIST_GROUP_UNITS` | 成立（**契约层已强制**，即 pass-1 F2 的“有界”半边已补） |
| 严格同格（新续读） | 构建器 `:1065` `following.table_context != unit.table_context`；契约 `:2634` 同一判据 + `heading_path` 相等 | 双点成立 |
| **不得引用外部来源** | 契约 `:2630` `following = {…(*owned_units, *context_units)}` → 不在本批的 id 命中 `unit is None` → `:2635` 抛“相邻原文读取范围必须逐项对应同格连续原文” | 确定性成立（测试 `:194-198` 伪造 `["foreign"]` 被拒） |
| **不得非相邻** | 契约 `:2631-2634` 逐项 `offset` 从 1 起、要求 `source_ref == f"{prefix}.p{int(paragraph)+offset}"`——**禁止跳跃、禁止乱序，允许真实前缀截断** | 确定性成立（正确的语义：前缀合法、缺口非法） |
| 只能归属本批引言 | 契约 `:2621-2622` `set(bounds) <= set(owned_ids)`；`:2623-2627` 引言必须 `.p<digits>` 且有 `table_context` | 成立 |
| **完整性不可声明** | `complete_list_asserted: Literal[False] = False`（`:2533`）——**schema 层使“清单完整”不可表述**；测试 `:191-193` 把它改成 `True` 直接 `ValidationError` | 成立：比 pass-1 我建议的布尔标记更强（更强正向） |
| 投射进 source/author 输入 | `protocol_control_deconstructor.py:2912-2913`：`not frozen_input.table_context_reading_bounds` → **弹出该键**（历史形状不变）；否则留在 `input_view` 供模型看到真实范围与停止原因（`:2955`） | 成立 |
| **模型被明确告知“前缀不是全表”** | `:2951-2953`：“相邻表格原文仅为有界只读片段；table_context_reading_bounds 记录实际读取范围及停止原因，**不证明清单已完整**。**不可把预算截断或位置边界解释为清单结尾**；范围不能核清时保留具体未决。” 测试 `:185-188` 对**两个**提示词都断言含“不证明清单”+stop_reason+`complete_list_asserted` | 成立（两个提示词都覆盖） |
| 保存进批次 | 构建器 `:1272-1279` 传 `all_units=coverage_manifest.units` 与同一 dict；`:1306-1322` 只为 `owned_ids ∩ continuation_bounds` 建批次字段 | 成立 |
| 空元数据不改变历史形状 | `exclude_if=lambda value: not value`（`:2559`）机制可见；`no_intro/plain_paragraph` 两个边界**不记录**（构建器 `:1052-1054` `continue`）→ 若建批次则为空 dict → 序列化省略 | **机制成立；“material identity 不变”未验证**（见 §8 Q2） |
| 宿主边界不是模型临床结论 | 停止原因与范围 ID 全程由宿主计算（planning）、宿主校验（contracts），在提示词中作为**宿主提供的事实**出现，并附“不得解释为结尾/不证明完整”的约束；窗口内没有任何提示要求模型*声明*完整性或把范围转成临床结论 | 成立 |

**F6 残余（低）**：契约镜像了**单元数**预算（`:2628-2629`）但未镜像**字符**预算；即一个重建/编辑后的批次可在“MAX 条同格连续原文”内超出 `_MAX_SCHEDULE_ROW_CONTEXT_CHARS`。①`stop_reason="character_limit"` 仍会被记录，②excerpt 属冻结单元（改文本另有其它校验拦），故**无可证的可达路径**；我将其列为可选加固（1 行 import + 1 行判据），不作为本轮要求。

---

### 3. 其余处置记录

- **F2**：接受。新续读在构建器与契约**双点**同格（`:1065` / `:2634`），并有 `cell_metadata` 用例（仅改 `table_context.column_headers`、`source_ref` 前缀不变）证明**纯元数据差异即停止**——这正是 pass-1 我指出的“只由模型相等守住的路径未被证明”。pass-1 同时提到的 `table_row_key` 双份实现（`planning:966-974` 与 `contracts:2923-2931`）本窗口未处理：**可选**去重，不构成缺陷。
- **F3/F4**：接受为窗口边界（创建侧证明官方谓词 ID + 发布侧复核消费者）。残余如实记录：受限登记**回放/再校验**处仍不调用 `require_frozen_official_predicate_identities`，故*该回执自身的声明强度*由发布层兜底；不要求在本窗口扩建全局引用架构。
- **F5**：接受放弃。记录一个可审计性单点：`restricted_statements` 本身不带“同胞曾被核为 `covered_by_official/procedure` 但被整体撤回”的注记（pass-1 窗口 `367-399` 不读 `reviewed` 的结论未变），原始 review 记录仍在 run result/检查点中；这属临床/产品判断，我不再要求改动。
- **F10**：三项均已落地——fixture 坐标 `table_path=(10,1), row_index=10, column_index=1, member_cell_paths=[(10,1)]` 与 `body.t0.r10.c1.p{n}` 自洽（`:121-122`）；字符预算默认用例断言（`:160,166-170`）+ `unit_limit` 用例（`:115,140-142`）双覆盖；`enum` 化 `StructureUnitKind.TABLE_ROW`（`:120`）。硬编码 6000 已被 `_MAX_SCHEDULE_ROW_CONTEXT_CHARS` 取代（`:111,160`）。

---

### 4. 正向案例（本轮新增可复核证据）

1. **完整性在类型层不可声明**：`Literal[False]`（`:2533`）+ 篡改即 `ValidationError`（测试 `:191-193`）。这是“context truncation is not completion”的最强形式——不是约定，是不可表述。
2. **“无续读”也被记录**：`gap`/`other_cell`/`cell_metadata`/`heading` 情形下 `included_structure_unit_ids` 为空但 `stop_reason` 与 `complete_list_asserted=False` 照常写入（构建器 `:1068-1069` 先 break、`:1082-1086` 仍记录；测试 `:163-171`）。失败/未取到上下文**不会退化成沉默**。
3. **畸形原答逐字保留**：`declaration_rejected` 用例把原答设为 `"{"`，失败检查点仍断言 `raw_output_text == "{"`（`:631-632,673`）——诊断留证不因解析失败而丢证据。
4. **拒绝路径不依赖 stage**：`:678-682` 两种 stage 标签都抛 `PROTOCOL_CONTROL_CHECKPOINT_INVALID`；`retryable=False`（`:662`）杜绝自动重试生成假成功。
5. **空元数据短路**：`deconstructor:2912-2913` 在无界时**移除键**而非留空 dict，配合 `exclude_if` 形成“历史批次字节形状不变”的双保险（机制层面）。
6. **恢复是真实登记**：`:3485-3498` + `:3503-3504` 收据——恢复必然产生一次新的模型回答与其收据，而不是复用旧答复。
7. **前缀合法、缺口非法**：契约 `:2631-2634` 的 `offset` 链使“真实截断”可通过、“跳过一项”必抛（测试 `:194-198`）。这是对“有界 vs 完整”最贴切的编码。

---

### 5. 危害性案例（含可达路径与严重度）

| # | 场景 | 路径 | 后果 | 定级 |
|---|---|---|---|---|
| H1 | 失败检查点被**删除标记键**后重放 | `saved` 去掉 `restricted_registration_failed`/`schema_version`、stage 改 `deep` → `_replay_checkpoint`（**未读**）若只按键判定则放行 | 以“完成态”消费无有效登记的受限原文（pass-1 HC-1 形状） | **需 1 次读定性**；最小修复 2 行（并入派生条件） |
| H2 | 批次内**只有**宽松同表上下文、无任何 bound | 非“：”结尾的同格段落 → 不触发续读 → `table_context_reading_bounds` 为空 → `deconstructor:2952-2953` 的完整性告诫**不出现** | 模型可能把可见同表文本当作穷尽 | 低；**建议不改**（改会污染所有历史提示词身份，违背“只受影响批次获得新 identity”） |
| H3 | 模型把**上下文单元**当作自身 owned 证据引用 | 提示词现在显式把范围 ID 交给模型；上下文可跨批次复用（`contracts:2541-2543`） | 若校验器不拒绝“非 owned 单元”的陈述，则上下文可被提升为判定依据 | **未读依赖**（`validate_source_interpretation`），非本窗口新引入；仍是最值得点名的一项 |
| H4 | 续读最后一项是**下一个清单的引言** | `stop_reason="next_intro"`，该项被包含（测试 `:155-156,169`） | 若读者忽略 stop_reason，可能把下一清单引言论当作本清单项 | 低；`stop_reason` 已如实命名，属可读性风险 |
| H5 | 失败检查点的两份运行结果副本被**分别编辑** | 顶层展开 vs 嵌套 `run_result`（`:3455,3468`） | 两个读取器状态不一致 | 低·卫生（修复 2 行或 1 断言） |

---

### 6. 仍存在的具体缺陷 / 加固项（含最小修复与是否阻断）

1. **（唯一可能阻断，条件性）`_replay_checkpoint` 的拒绝谓词是否可派生** —— 见 H1。最小修复 2 行：把“`consumers is None` 且 `attempts` 非空（或 `attempts[-1].outcome != "parsed"`）”并入拒绝条件。**若谓词已含派生条件，则本项关闭。**
2. **（低·卫生）失败检查点运行结果双副本**：`:3454-3472` 单次计算共用；或测试加 1 断言。
3. **（低·可选）契约未镜像字符预算**：`:2628-2629` 旁增 1 行同款判据（import 常量）。
4. **（低·可选）稳定性断言缺口**（1–2 行级，全部非阻断）：
   - 成功路径无 `assert "restricted_registration_failed" not in saved and saved["stage"] == "deep"`（owner 本次要求验证的正是这条，目前仅由我读代码确认）；
   - 无 `assert "table_context_reading_bounds" not in emptied_batch.model_dump(mode="json")`（“历史形状不变”的关键机制只被间接覆盖，`no_intro/plain_paragraph` 直接跳过建批次，测试 `:163`）；
   - 失败检查点未显式断言 `source_target_review`/`attempts` 存活（仅断言 `source_interpretation`/`coverage`）。
5. **（记录·不改）** F3/F4 残余、F5 注记、H2 告诫范围、H4 尾项语义：均为已接受的窗口取舍，我不要求改动。

**结论：本轮新读代码内没有“可达路径 + 首要因果”的新缺陷。** 第 1 项是唯一还可能改变定性的点，且它需要一次未读窗口才能判定。

---

### 7. source/projection protection 与 clinical meaning 的分界（明确切分）

**已证（源码/契约/断言级，属来源与投影保护）**
- 失败登记：持久、带标记、双 stage 拒绝、保留真实来源/处置/原答、`retryable=False`、恢复必须走新的真实登记与当前门。
- 有界相邻读取：宿主计算、契约逐项校验（禁外部、禁非相邻、同格同标题、单位上限）、完整性在类型层不可声明、空元数据不改变历史序列化形状。
- 两个提示词都明示“有界、不证明完整、不得把截断/边界当结尾”。
- 宿主边界是宿主事实，不是模型临床结论。

**未证（不属来源保护，属临床/语义，明确不在本角色权限）**
- 模型是否**实际遵守**“不证明清单完整”的告诫（需模型调用；本轮明确排除）。
- 截断范围内的临床解读是否正确、清单项是否被正确归入某一要求。
- whole-unit 保留撤回同胞已核覆盖的**临床可接受性**（owner 已裁定；属产品/临床判断）。
- 官方谓词身份在受限登记回执层未再证的**临床等价性**（发布层兜底；owner 已裁定窗口边界）。
- 我读到的任何断言都**不是**测试通过证据；488/12/最终窗口不由我认证。

---

### 8. 对 Codex 的有界问题与请求（按性价比排序）

**Q1（最高优先，决定 H1 定性）** —— `_replay_checkpoint`（新测试 `:681` 引用）的**完整定义与拒绝谓词**在哪个窗口？它拒绝失败检查点的依据是①声明性键（`restricted_registration_failed`/`schema_version`/`stage`）、②运行状态派生条件、还是两者？
*为何重要*：若仅①，删除标记即可把失败诊断还原为“完成态”，pass-1 HC-1 在最窄形式下仍成立；若含②，F1 彻底闭合。
*请读*：`protocol_control_execution.py:1147-1244`（我因 8 次上限未读，最可能落点）或该函数实际所在区间。
*安全临时路径*：无论答案如何，先落 2 行派生谓词加固（§6-1），成本极低且不改变任何现有断言。

**Q2** —— “只有受影响批次获得新 material identity”的**比较函数**在哪？请给出行窗（候选：`_same_deep_batch_material`，pass-1 窗口 `2053-2056` 仅见函数头）。
*为何重要*：这是 owner 关于“历史批次身份不变”的**唯一未验证**主张；`exclude_if` 机制我已确认，但复用比较未读。

**Q3（高价值）** —— `app/agents/protocol_control_source_interpretation.py:2578-2608` 是否包含 `build_source_interpretation_prompt` 的**有界告诫副本**？若是：它与 `deconstructor:2951-2953` 是**同一常量**还是两份中文文本？
*为何重要*：测试 `:185-188` 只能证明“两者都出现”，不能证明两者**语义一致**；两份文案漂移会让 author 侧与 source 侧对截断的理解分叉（成本：1 次读）。
*建议*：若为两份，抽同一常量；这属 1 行级去重，不是重构。

**Q4（承接 pass-1，仍未闭合）** —— `validate_source_interpretation`（或发布门）是否拒绝“陈述/引用的 `structure_unit_id` 仅为 context 单元（非 owned）”？
*为何重要*：F6 把范围 ID **显式**交给模型后，H3“上下文被提升为判定依据”的暴露面变大；这是“上下文只读、不转移所有权”从*结构*变成*行为*的唯一缺口。

**Q5（决策点，非请求）** —— H2：是否接受“无 bound 时不给完整性告诫”的现状？我的建议是**接受且不改**，理由是改动会改变所有历史提示词身份，违背本轮“只影响受影响批次”的原则。请确认该取舍进入决议记录，以免日后被当作遗漏。

**Q6（对目标打包方式的复核建议）** —— 本轮把“失败登记耐久性（已闭环）”与“有界相邻读取（机制/契约/提示词均已闭环，material identity 未验证）”放在同一对象里评估，二者成熟度不同；建议在决议记录中**分开落条**，并明确 Q1/Q2/Q3 为待补读项，而不以“本对象通过”覆盖它们。

---

### 9. 与 owner 陈述的差异点汇总（便于 Codex 快速对齐）

| owner 陈述 | 我的复核结果 |
|---|---|
| “failed registration 持久为 deep_failure_diagnostic/v3” | 一致（`:3455-3460`，测试 `:664-666`） |
| “保留 actual source/review/attempts/private raw answers 与失败标记” | 一致；review/attempts 由构造保证，测试仅显式断言 source+coverage+raw（§6-4 小补） |
| “即使 stage 误标 deep 也不能通过 completed replay” | **行为一致**；拒绝机制未读（Q1） |
| “成功检查点仍为 deep 且无失败标记” | 一致（构造保证）；无显式断言 |
| “空元数据不参与序列化以保持历史形状” | 机制一致（`exclude_if` + 空即不记录）；“只有受影响批次获得新 material identity”未验证（Q2） |
| “新续读严格同格且坐标/标题有界” | 一致（构建器+契约双点，测试 `cell_metadata`） |
| “模型被明确告知前缀不是完整清单” | 一致（`:2951-2953`，两提示词断言 `:185-188`） |
| “宿主边界不是模型临床主张” | 一致 |

**不声称最终验收。** 本报告仅为有界咨询意见与可复核证据；临床采用、完整 Job 成功、最终交付与任何测试通过数均不由本角色裁定。
