Trellis SessionStart 上下文已加载。收到会议审查任务：对两文件工作补丁（相对 HEAD `ed4f5c4a0bb997649e40395733f379a7a8025d96`）做只读审查。先获取受限 diff 与文件状态。

Bash 权限在非交互模式下被拒绝，无法直接运行 `git diff`。改用只读工具（Glob/Grep/Read）完成审查，并先查找 runner 是否提供了补丁或差异材料。

报告路径已存在（当前会议自己的文件，非他会议历史）。先查看工作区中可能存在的补丁材料与关键源码。

Runner 上下文只有占位 TODO，没有提供补丁文件；Bash 被拒无法运行 `git diff`。改用完整读取受影响定义 + 查找版本标记来重建 v7→v8 变更，并在报告中声明该限制。现在读取三个源码文件。

文件很大（~10k+ 行）。定位并顺序读取关键区域。

读取宿主合并与恢复函数。

读取传输契约与恢复身份相关消费方。

读取 runner 选择/恢复路径与 v8 相关测试。

现在读取申报的关键测试段。

# Conference Output: rv1006-source-insert-delta-review-20261008 - evidence_single_object

## Output

### 0. Scope, method, evidence boundary

- 只读审查，未修改任何文件、未运行测试、未发起任何模型/网络调用、未读取 `.env`/数据库/临床原件/其他会商历史。
- **限制（重要）**：本会话 Bash 权限被拒（非交互模式），因此**无法执行 `git diff` vs `ed4f5c4a0bb997649e40395733f379a7a8025d96`**。v7→v8 的"引入 vs 既有"判断依据是代码内版本标记（`_SOURCE_INSERT_GUIDANCE_VERSION = "phase5/source-insert-guidance/v8"`，`app/agents/protocol_control_deconstructor.py:2288`）、注释、测试现状与任务描述，**不能证明逐行差异**。
- Owner 声称的工件 `artifacts/rv1006-source-insert-delta-connected-20261008-v2.xml` 在本 worktree 内用 `**/*delta-connected*` 未找到；`runs/conference/.../evidence_single_object.md` 仅为 PENDING 占位。**32 passed / 1089 deselected 未经我复核**（不质疑，仅声明未验证）。
- 审查范围：题面两个文件 + 允许的消费方（transport 契约、execution 恢复身份、两个测试文件的相关段落）。未追踪完整发布门、front-stage flow、restricted batch。

### 1. 四个挑战点的裁定（先说结论）

**C1 delta 与 legacy full-wire 的输出契约一致性：AGREE，一处小瑕疵（不阻塞）。**
- 单一增量且授权单元处置在 4 类白名单内 → `source_insert_candidate_only`；否则多候选 delta；仅当 transport 缺 `continue_candidate`/`continue_candidates`/`start_source_insert` 时落到 legacy full-wire（`protocol_control_deconstructor.py:10307-10336`）。
- Delta 指令与 schema 一致：prompt 只允许 `candidate_draft(s)`（`:3174-3184`），`_merge_source_candidate_insert` 只接受这两种 payload（`:6104-6107`）；fresh 走 `continue_candidate`/`continue_candidates`（`:10552-10570`），resumed 走 `start_source_insert(multiple=…)`，其 response_format 与 single/multi 一一对应（`protocol_control_agent_transport.py:1529-1557`、`:1559-1590`、`:1800-1830`）。
- Legacy 指令要求"旧候选逐字保留、只在末尾新增、旧处置除授权单元外不变"（`:3138-3140`），与 `allow_source_insert=True` 分支的强制检查一致（`:4943-5004`）。
- 小瑕疵：single 端点（response schema 仅 `candidate_draft`）在 `json_object` 回退模式下若返回 `candidate_drafts` 数组仍被接受（merge 同时接受两形），属宽松一步，无静默风险。

**C2 官方/流程链接保留与不可变兄弟（fresh/resumed）：AGREE。**
- Delta 合并由宿主执行重分类：授权单元 → `other_control_candidate`、清空 `linked_official_code`/`linked_procedure_catalog_item_id(s)`/`notes`（`:6152-6160`），与 prompt 中"系统会将该单元改为其他控制候选并清除原处置链接"（`:3146-3148`）一致。
- 原目标关系由宿主强制：旧 `OFFICIAL_ELIGIBILITY` → 需 `official_rule` + `official_code`；旧 `REQUIRED_PROCEDURE` → 需覆盖全部 `linked_procedure_catalog_item_ids`（或 legacy 单字段）（`:4971-5004`）。测试直接覆盖：`:6120-6165`（保留通过、删关系 → `REPAIR_SCOPE_ESCAPE`）、`:6167-6196`（多候选 + 缺目标拒绝）。
- 兄弟不可变：candidate 前缀逐字相等 + 长度增长（`:4949-4952`）、范围外处置逐字相等且顺序不变（`:4953-4963`）；另有 hydrated 层漂移门（`:4832-4916`）。
- Resumed 路径：`start_source_insert` 新会话 + "已核候选只供去重"（`:10467-10475`），每轮都重跑原始追加授权检查（`:7843-7851`，注释明确 "Repair mode can change; the original append authority cannot"）。测试 `:6846-6955` 覆盖 restored 分支。
- 残留差异（低）：delta 在合并处强制"新候选并集 == 授权单元"（`:6139-6140`）；legacy 分支不做全量覆盖断言（`:4964-4970` 仅逐候选 ⊆ 与相交），依赖下游 source-statement coverage 门。两路径强度不同，但 legacy 仅用于能力降级的 transport。

**C3 scope 逃逸/重复插入/来源覆盖仍被拒：AGREE（有一处既有语义空白）。**
- 单元/span 范围：`:6136-6137`、`:3671-3689`（`CANDIDATE_SOURCE_SCOPE_ESCAPE`/`CANDIDATE_SOURCE_UNIT_SCOPE_ESCAPE`）。
- 覆盖：并集必须等于授权集合（`:6139-6140`）。
- 精确重复：hydrate 时全 JSON 指纹去重 `DUPLICATE_CANDIDATE`（`:3692-3700`）；"已引用但未证明表达"则停止补入转需要核对（`:9210-9253`）。插入上限 `MAX_SOURCE_INSERT_REPAIRS = 2`（`:166`、`:9263-9288`、`:10214-10216`）。
- 语义近似重复（措辞不同、含义重叠）没有确定性拒绝，依赖 target review/coverage 语义门；这是既有分工（确定性校验管结构，语义归 bounded review），不是 v8 引入。

**C4 v8 修复身份影响：与声称一致，但有两个"未声称"的附带影响（见 D2）。**
- `_SOURCE_INSERT_GUIDANCE_VERSION` 进入修复合同哈希（`:2888-2911`，v7→v8 改变哈希）。
- 完成态检查点：`repair_used=False` → 哈希不参与（`protocol_control_execution.py:3190-3191`，可与当前 revalidation 一起复用）；`repair_used=True` → 必须等于当前哈希或旧代际哈希且错误类不相交（`:3192-3225`，`SOURCE_INSERT_INVALID` 属 `old_base` 受影响集 `:3211-3213`）。旧 v7 回执不匹配任何**当前重算**的旧代际哈希 → 拒绝（`reused` 计划理由 `repair_material_changed_or_unproven`，`:3037-3044`）。**旧修复输出不会被静默信任。**
- 版本号只影响修复材料、不影响 author 材料的约定有测试守门（`tests/v2/services/test_protocol_control_execution.py:251-259`），`_repair_material_matches` 复用矩阵测试在 `:5329-5410`。

### 2. 我主动发现的问题（按影响排序）

**D1（最高影响缺陷候选，既有根因、v8 未确认引入）— 选择与合并在"白名单外处置"上互相矛盾，必然落入 需要核对。**
- `source_insert_candidate_only` 要求授权单元处置 ⊆ {supporting_or_supplement, other_control_candidate, official_eligibility, required_procedure}（`:10316-10325`）；不满足时（**含单条声明**）`source_insert_candidates_only` 仍会选中 delta（`:10327-10335`）；而合并对同一集合有同名硬性拒绝（`:6142-6151`），异常 `SOURCE_INSERT_INVALID` 不带 scope → `repair_scope_unknown`（`:9755-9767`）→ 直接 需要核对。
- 含义：若真实批次存在"补充声明挂在白名单外处置单元（如 post_treatment_execution）"的情形，v8 的 delta 端点**确定性地无法完成**，且会消耗一次模型轮次；而 legacy full-wire 分支的 `allow_source_insert` 检查对非 {REQUIRED_PROCEDURE, OFFICIAL_ELIGIBILITY} 单元并不禁止重分类（`:4972-4983`），即两个端点在**同一政策问题上给出相反答案**。
- 最小修法（二选一，均<10 行）：(a) 若以 fail-closed 为准：把 4 类白名单条件同样加到 `source_insert_candidates_only` 的选择上，或在派发前用带 scope 的类型化错误提前终止（避免无效模型调用）；(b) 若允许转换：删除/放宽合并白名单并补一条"notes 必须可丢弃"的说明。
- 需 Codex 裁定（Q1/Q3）。

**D2（恢复行为附带影响，机制既有、v8 触发一次代际跨越）— 在途局部草稿与旧代际"宽限"回执。**
- 同任务重试路径对 `deep_failure_diagnostic/v3` 强制 `repair_contract_sha256 == 当前值`（`protocol_control_execution.py:3813-3814`），不区分 `repair_used`；v8 之后，v7 时保存的**无修复**在途 partial wire 也会被 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID`（retryable=False）拒绝，比 `_repair_material_matches` 的语义更严。
- 跨任务复用路径是宽容的：哈希不符 → 丢弃 wire、仅重导出 source seed（`:2642-2659`），不硬失败。因此影响取决于编排层如何消费该 StepFailure（我未验证）。
- "宽限"机制（`old_atom`/`old_current`/`old_base`）用**当前**模块重算，任何版本串上调都会使历史回执退出宽限集合——这是既有设计属性，v8 只是又触发一次；方向仍是 fail-closed。
- 最小修法：不要求改代码即可安全上线；若运维需要保留在途恢复连续性，最小改动是让直接恢复路径与 `_repair_material_matches` 对齐（无修复 → 允许身份漂移后按当前 revalidation 恢复），或把旧诊断显式降级到 `_validated_deep_partial_source` 的 seed 路径。请 Codex 决定（Q2）。

**D3（低，健壮性）**：delta payload 若为 `{"candidate_draft": <非 dict>}`，`_complete_evidence_source_pairs_from_atoms(draft)` 会触发 AttributeError，而合并的 except 元组未含 AttributeError（`:6171`）；好在主循环 `:9495` 的 `except Exception` 兜底为 bounded validation 边界，结果仍是 fail-closed，只是错误标签不精确。一行修复即可（把 AttributeError 加入 except 元组或先做 `isinstance(dict)` 校验）。

### 3. 我不下结论 / 未验证的部分（明确清单）

1. **未验证** `git diff`：哪些行是 v8 新增无法机械证明；D1/D2 是否为 v8 引入不能断言（D1 我倾向既有、D2 是 v8 触发）。
2. **未验证** 测试结果与工件（32 passed/1089 deselected、`rv1006-...-v2.xml` 不存在于本 worktree；亦未运行任何测试）。
3. **未验证** 真实 transport 的 structured-output 模式（`json_schema` vs `json_object`）下 provider 实际行为，以及 `start_source_insert` 的 schema 注入路径在生产的实际命中率。
4. **未验证** 除 `_validate_saved_source_review`（:3243-3296）之外的 OTHER_CONTROL_CANDIDATE+relations 消费方：完整发布门、front-stage flow、restricted batch、外部报告导出。
5. **未验证** 编排层对 `retryable=False` 的 `PROTOCOL_CONTROL_DEEP_SOURCE_INVALID` 的处理（是否自动转 failed_final 后经复用计划重建）——这决定 D2 的实际代价。
6. **未验证** `MAX_SOURCE_INSERT_REPAIRS` 耗尽后跨"作业恢复"是否重置，以及多轮插入间的近重复语义拦截（仅验证到 `cited_unexpressed` 停止路径）。
7. 未阅读 `.env`、数据库、临床原件、其他会商历史；无网络/模型调用。

### 4. 结论（临时的，非验收）

在被审窗口内**未发现临床逻辑、权限或门限的静默放松**：delta 只提交候选、宿主负责重分类并强制保留原官方/流程关系；scope 逃逸、覆盖缺口、精确重复、插入超限与合并拒绝均 fail-closed 到"需要核对"。C1–C4 的声明在代码与测试层面**基本成立**。需要 Codex 裁定的仅 D1（选择与合并的白名单矛盾）与 D2（在途局部草稿的严格身份导致的恢复代价），两者都有 <10 行的最小修法，无需新通用框架，也无需再次临床批准。

### 5. 给 Codex 的边界提问

- **Q1**：补充声明的授权单元处置在白名单外时，权威语义是"必须 fail-closed 需要核对"还是"允许重分类为 other_control_candidate"？前者请把白名单前置到 `source_insert_candidates_only` 选择（或类型化前置错误），后者请放宽合并白名单。
- **Q2**：是否要求 v7 时代保存的 **无修复在途 partial wire** 在 v8 后可继续恢复？若是，是否接受把 `:3813-3814` 的严格等值改为 `_repair_material_matches` 等价语义（无修复→当前 revalidation 后可续；有修复→拒绝）？
- **Q3**：真实 RV1006 批次中是否存在把 `SOURCE_TARGET_ADDITIONAL_REQUIREMENT` 声明挂到白名单外单元的证据？若无，D1 仅防御性，可不改，只需在窗口记录为已知边界。

（本角色未修改任何文件；以上为完整报告，供 runner 落盘。）
