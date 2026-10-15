Trellis SessionStart 上下文已加载。开始冻结窗口只读审阅（基线 28858ba；上限 15 次读取；不派工、不运行、不改文件；git diff 早前权限拒绝，不再重试，以实际定义与测试为据并声明边界）。先定位六处改动点。

定位完成（decon 形状/合并 1744-1798、7073-7236，runner 10416-10452；transport 1712；alignment 辅助 248-278；experiment 96-160；identity 事件间隔版本需核）。并行读取六区。

补最后三处：`_matches_time_anchor_direction` 调用点是否传 source、字段补丁/事件间隔测试族、transport 三格式测试。

Trellis SessionStart 上下文已加载。冻结窗口只读审阅完成（15/15 次读取用尽；未运行测试/模型/服务、未改文件、未派工；git diff 因非交互权限早前被拒、未再尝试——差异以当前实际定义与测试为据；报告不复述任何原文）。按 已证/必修/建议/未验 分列。

## 一、已证（源码+测试直接支持）

**A. 形状、合并与 Runner（deconstructor）**
1. 紧凑字段 Schema（1743-1807）：`repeat_scheme_only` 生成 `RepeatEvaluationPatch`——**仅** `repeat_scheme`、`required` 全含、`additionalProperties:False`、根仅 `evaluation_patch`，并按可达 `$defs` 剪枝；与 numeric patch 互斥（1750-1751）。
2. 合并两条兼容路径（7073-7154）：
   - `evaluation_patch` 路径：只允 `{repeat_scheme}`（7085-7087）；`frozen_atom` 取自**基线**并仅 `update(patch)`（7094-7095）→ 其余字段由构造即来自冻结原子，**无法改兄弟或改其他字段**；负例 extra_field/missing/null/旧版本/结果采用矛盾在测试 529-553 全部拒绝。
   - 旧完整 atom 兼容：通用字段逐一比对（kind/statement/modality/来源/后续义务等，7118-7124）；repeat 分支要求时间约束不变、原 scheme 为空、`require_current_extraction()`、其余 evaluation 字段不变（7132-7141）。
   - 合并以 `ProtocolControlAgentWire.model_validate` 收口（7149）；异常统一 `ATOM_REPAIR_INVALID`（7150-7154）→ 上层 return 需要核对（10453-10466），fail-closed。
3. Runner（10411-10476）：`patch_reader` **优先 `continue_repeat_scheme`**，其次 numeric，再退 `continue_atom`（10421-10423）；单错误/单声明/∈cited_unexpressed/预算/路径去重/单次计费/会话一致/attempt 保存/基线回退全部与上一窗口一致（10424-10475；回退见 7614-7618 上窗已读）。
4. 测试（488-526）：atom 恰一次调用；无兄弟成功→采用（与原线仅差 scheme）；**有兄弟未决→final 为空、partial_wire 逐字等于原线、重新对齐两次、parsed attempt、兄弟候选未改**；numeric/scoped reader 禁用。

**B. Transport（1698-1748）**
- `continue_repeat_scheme` 委托同一 `_continue_atom_repair(repeat_scheme_only=True)`（1712-1718）；会话门=真实历史或 scoped 绑定（1727-1728）；**仅发单条 user 消息**（1735；注释 1729-1730 明确不携带整批历史），不写 `_histories`（1747 注释）。
- 测试（transport 1306-1335，`text/json_object/json_schema` × repeat/非 repeat）：会话不变、`history()` 前后相等、调用仅 1 条消息、json_schema 的名字/字段集/required/additionalProperties/defs 剪枝逐项断言，非 strict 模式把紧凑 schema 嵌单条消息且 `response_format` 形态正确。✓ 无新通道/新作业/新框架。

**C. 来源事件间隔例外（candidate_alignment 248-278；调用点 978、984 均传 `source=source`）**
- 例外仅当：**无任何已命名锚点**、恰一个方向、词长>2、非数字词；且原子 `anchor_type=="event_date"`（260）、方向匹配（261）、**所有界限字段为 None**（lower/upper days、lower/upper bounds、half_life、combined_window，262-264）、`determination_mode=="semantic"` 且 `time_purpose=="interval_condition"`（265-266）、词同时保留于 atom.statement 与 spec.proposition（267-268）、并**原子与求值均携带与 source 逐字相等的当前来源**（269-271）。
- 命名锚点存在→走旧分支（274-278，锚点必须匹配该命名锚点）：**EVENT_DATE 不能顶替筛选/基线等固定锚点**（反例 `visit_substitution` 589；测试 599-601 拒）。
- 其它反例全拒（563-601）：方向相反、命题少词、求值来源不同、带数值窗、可执行目的（event_membership）、模糊无方向词。
- 正例（602-607）：validate 通过并绑定 proof 后，消费者 `_proposition_observation` 仍返回 **UNKNOWN + `interval_calculation_unsupported`**——**表示完整≠可求值/已采用**，已由测试钉住。

**D. 消费者缺口保护（experiment 96-167）**
- `_proposition_observation` 117-118 与 `_conditional_observation` 148-149：`interval_condition` 一律 UNKNOWN + `interval_calculation_unsupported`；投影测试族（test_control_interval_semantics 39/49/98/101/119）持续断言 UNKNOWN。未开发算法、未移除保护。

**E. 身份与旧 proof（alignment 590-635；execution 121、2135）**
- `_alignment_input_identity` 在候选任一义务原子有 `event_date` 锚点时加入 `event_interval_alignment: SOURCE_EVENT_INTERVAL_ALIGNMENT_VERSION`（614-617）→ 无此键的旧 proof 摘要不匹配（复用机制上窗已证 694-735）→ 丢弃并重核；execution 组成列表追加该版本（2135，import 121）。

**F. 首窗 2 fail 的已修项**
- `_matches_time_anchor_direction` 函数体内已有局部 `normalize_source_excerpt` 导入（249）——与模块既有局部导入习惯一致；两个失败应属该缺失，重跑前不宣称通过。

## 二、必修

**无源码证据的必修项。** 逐项核对均未发现：误把有源表示当可求值/已采用（C/F 测试）、绕未知依赖（例外不改 unresolved，消费者 UNKNOWN）、EVENT_DATE 顶替固定锚点（C）、字段补丁改兄弟或混淆允许/必须（A 构造+frozen、许可-力对齐在上窗 461-464 仍在）、旧失败/身份/预算丢失（A/B 与上窗一致）。

## 三、建议（含最小反例与消费者）

- **S1（失效面略宽）**：身份键按"任一原子有 event_date 锚点"加入（614-617），而非"新例外实际生效"。危险反例：候选含无关 event_date 原子 → 旧 proof 全部失效，多一次重核调用（仅成本，方向 fail-closed）。若需收窄：条件改为"存在 event_date+interval_condition+全界限为空"的原子；消费者：`reusable_proven_alignment_items`、对齐重核预算。
- **S2（文档）**：在 `_matches_time_anchor_direction` 注释中显式写明"仅放行有源时间表示；可求值性由消费者保持 UNKNOWN；不得用于替换命名锚点"，便于后续维护者不误扩。
- **S3（测试补充）**：为字段补丁补一条"payload 携带 atom 而非 evaluation_patch、且 repeat_scheme_only=True"的兼容负例/正例（当前 529-560 只测 patch 形态；488-526 的 field_patch 变量覆盖 runner 侧）。

## 四、未验

- 字段补丁通道的 validator 组成条目未逐行读取（本轮仅证事件间隔版本 2135/121 与上窗条目；无法精确列出本轮新增的全部常量）。
- `_conditional_observation` 167 行之后未读完（interval_condition 分支已证）；git diff 不可用（权限拒绝）；测试未运行（95/2 为用户口径，修复未由我复验）；未读原件，不声称任何临床含义。

本轮为只读审阅、未新建任务；按工作流征询：本回合是否需要建立 Trellis 任务（如不建，本报告即本窗口终稿，后续仅在指定新窗口继续只读核对）？
