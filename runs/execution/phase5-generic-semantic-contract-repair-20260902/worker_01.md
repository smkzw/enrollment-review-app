# 执行输出: phase5-generic-semantic-contract-repair-20260902 - worker_01

## 边界与上下文检查

- Runner 的 CWD 绑定到工作树 `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`；所有读取和写入均保留在其中。
- 已读取初始读取集 (`context/..._execution_context.md`, `plans/codex_execution_....md`)。上下文的 "Source Of Truth" 部分是 Codex TODO，未列出任何文件，因此我自行定位了语义提示词合同：它由 `app/agents/protocol_deconstructor.py` 中的三个常量 `_SYSTEM_CONTRACT`、`_FORMAL_DOMAIN_ID_CONTRACT`、`_COMPACT_WIRE_COMPONENT_CONTRACT` 组成，并通过 `protocol_prompt_template_sha256()` 以及每一个批量/修复/片段提示词组装进行哈希处理。额外的读取，均为我分配任务所需的：`app/protocols/deconstruction_gate.py` (只读，用于对齐提示词措辞和门控不变量)，`.trellis/workspace/codex/journal-2.md` (会话 90–101，用于预先存在的失败基线)，`tests/v2/protocols/test_protocol_transport_transient_retry.py` 和 `test_generic_semantic_contract_fault_injection.py` (失败归因)。
- 仅修改了分配的工件：`app/agents/protocol_deconstructor.py`（仅提示词合同字符串）。未修改门控 (`worker_02` 的范围)、测试 (`worker_03` 的范围) 或任何生产/临床数据。未分发执行管理器；未召开会议。

## 已执行工作

审查了提示词合同与确定性门控，发现并修复了四个指令区域（+ 一个与路由目标和 `worker_03` 锁定的测试一致的连接器）。所有措辞均为通用中文；未写入特定项目的临床规则。

1. **非限制性人群范围** (`_SYSTEM_CONTRACT`): 扩展了 "‘性别不限’不是入组限制，不得虚构为男/女分类原子" → "‘性别不限’、‘男女不限’等非限制性人群描述不是入组限制，不得虚构为男/女分类原子或性别 exists 原子，也不得为其生成资料要求。"
2. **数值 `source_term` 逐字要求** (`_SYSTEM_CONTRACT`): 旧文本 "数值谓词在 source_term 仅填写原文中的指标名称" 缺少门控强制要求的逐字和绑定语义 (`METRIC_NOT_IN_SOURCE`, `METRIC_SOURCE_TERM_NOT_METRIC`)。新文本: "数值谓词的 source_term 必须逐字复制当前分支原文中的指标名称，并与 subject/attribute 绑定同一被测对象，不得用‘岁’、‘月’、‘ULN’等单位或阈值代替指标名" — 现在与紧凑导线合同及门控保持一致。
3. **共享期间来源绑定** (`_SYSTEM_CONTRACT`): 旧的禁令 "不得把同一子规则中其他分支的‘随机前’套入当前谓词" 与门控的 `SHARED_TIME_QUALIFIER_NOT_BOUND` 操作冲突，该操作指示模型在真正共享时*保留*时间窗并逐字绑定共享限定词。新文本: "当父级引导语或并列分支共享的一处时间限定语（如统一的‘随机前N周内’）确实统辖当前谓词时，应保留对应 time_constraint，并把共享限定语片段与当前分支自身文字分别逐字填入 source_clauses；仅出现在兄弟分支、不统辖当前谓词的‘随机前’不得套入" — 镜像了现有的共享指标名称绑定模式，并防止了过度表达和漏掉时间窗的故障 (`TIME_QUALIFIER_DROPPED`, `TIME_ANCHOR_MISSING`)。
4. **否定对象命名**（两个常量）：紧凑合同中的旧否定标记列表 "无/未/不/非/除外/排除/否认/阴性" 与门控不一致 — 门控明确将‘阴性’/‘不良事件’/‘非特异性’视为分类内容，将‘除外/排除’视为异常语义，并且对于 `negated=true`，要求否定词直接管辖通过 `source_term/attribute` 命名的对象 (`_source_supports_predicate_negation`)。已重写为：“否定词直接统辖该 atom 所指对象时，才允许使用 negated=true、ne 或 not_in：negated=true 要求‘无/没有/否认/未见/未使用/未接受/不存在’等否定词与该对象以 source_term/attribute 逐字命名的名称直接相连；not_in 的每个 values 都必须是紧随‘不属于/不在/不包括/非’等否定词之后的逐字分类值；ne 只对应原文‘≠/不等于/不是’加逐字比较值。‘阴性’、‘不良事件’、‘非特异性’等结果词或词内前缀是原文分类内容，不是否定标记”。在 `_SYSTEM_CONTRACT` 中添加了一句匹配的通用内容（此前对否定无指导）。
5. **明示替代连接语 "之一"** (`_SYSTEM_CONTRACT` ×2, `_COMPACT_WIRE_COMPONENT_CONTRACT` ×2): "或/任一" → "或/任一/之一" 在连接器列表中。满足路由目标和 `worker_03` 锁定的测试 `test_semantic_prompt_contract_names_explicit_alternative_marker`。

## 工件与证据

- 已修改: `app/agents/protocol_deconstructor.py` — 5 处编辑，全部在两个提示词合同常量内。注意：该文件在会话前已经包含了大量未提交的第 5 阶段工作（与 HEAD 相比 `git diff` = +3053/−111）；我的贡献仅是上述 5 处编辑。
- 观察到的新的动态提示词哈希值（template="x"）：`8b915ca4ef2d02c36213cc252a43177b158a53ab395810e0391b44fb0d4e642a`。没有静态测试固定当前哈希值；唯一固定的哈希是不变的 D001 历史锚点（见下文）。
- 新提示词措辞针对的门控不变量（只读证据）：`NEGATION_NOT_BOUND_TO_SOURCE` / `NEGATIVE_COMPARATOR_NOT_BOUND_TO_SOURCE` (`deconstruction_gate.py:1384-1415`, `_source_supports_predicate_negation` 位于 :461, `_source_supports_negative_comparator` 位于 :523), `METRIC_NOT_IN_SOURCE` / `METRIC_SOURCE_TERM_NOT_METRIC` (:1646-1698), `SHARED_TIME_QUALIFIER_NOT_BOUND` (:2276-2284), `TIME_QUALIFIER_DROPPED` (:1949-1962)。

## 命令与观察

- `python3 -m py_compile app/agents/protocol_deconstructor.py` → OK；对文件执行 `git diff --check` → 无问题（仓库范围的 `diff-check` 在文档/计划中存在预先存在的尾随空白违规，非我所为）。
- 通过 `.venv/bin/python` 渲染连接的合同字符串 → 所有修改部分阅读连贯；对新的措辞进行断言脚本检查 → 所有区域均存在，旧的不一致标记列表已移除。
- `.venv/bin/python -m pytest tests/v2/protocols/test_protocol_deconstructor_adapter_slice3.py` → 56 通过；在使用 `worker_03` 锁定的测试重新运行后 → 57 通过。
- 完整的 `tests/v2/protocols` 套件**伴随**我的修改：2 失败 / 1322 通过（复现两次，带和不带 `-p no:randomly`）。失败归因：
  - `test_d001_p803_p805_read_only_checkpoint_rebuilds` — 已知的、预先存在的不可变 D001 历史提示词 SHA 锚点失败（记录在日志会话 96–100 中）；按项目惯例保留。
  - `test_retry_warnings_preserve_chinese_recovery_semantics` — 单独通过（文件 14/14 通过），并在**有和没有**我的修改的全套测试顺序中失败相同（我进行了基准比较，通过回滚并重新应用我的 5 处编辑）：这是测试套件中预先存在的顺序干扰，并非由本次任务引起。
- `worker_03` 的 `test_generic_semantic_contract_fault_injection.py` 在我的修改下：29 通过 / 2 失败；失败的 2 个是 `test_structural_lead_in_segments_are_not_obligations[*]` — 属于 `worker_02` 的门控分配，正在进行中。并发已在 `mtimes` 中确认（`gate` 02:11:47，故障注入文件 02:12:53，我的文件 02:15:57），并且该文件在会话中期出现（早先的测试收集运行中不存在；全套收集数量从 1324 增加到 1355）。

## 阻碍或缺失的环境

- 无阻碍。注意：系统 `python3` 是 3.9，无法导入合同包；必须使用 `.venv/bin/python` (3.12)。
- 交叉工作依赖（推断，用于 Codex 协调）：在阅读时，门控的 `_has_unambiguous_disjunction` 接受 任一/任何一项/至少一项/和/或/及/或，但**不**接受 之一。我的提示词现在允许 一下 分支拆分；`worker_02` 必须在门控侧也接受 之一，否则会在相反方向重新打开提示词与门控的不匹配（提示词允许，门控拒绝）。

## 重跑请求或下一步

- `worker_02` 合并后：重新运行 `tests/v2/protocols` — 预期剩余的 2 个结构导入失败将关闭，套件最多返回到已知的 D001 锚点失败；建议单独调查 `transport-retry` 顺序干扰（未分配给我）。
- `worker_03` 的故障注入文件正在演进中；其测试的最终交叉验证以及所有三个工件的验收归 Codex 所有。
