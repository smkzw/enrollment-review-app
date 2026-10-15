# 执行输出：fact-correction-gap-replay-20260910 - worker_01 (implementation pass)

## 边界与上下文检查

- 所有工作均在运行时绑定的 `worktree` 中进行。写入操作仅限于四个已授权路径：`app/services/fact_correction_service.py`, `app/services/fact_normalization_executor.py`, `app/services/fact_expectation_gaps.py` (新建), `tests/v2/services/test_fact_correction_gap_reprojection.py`。
- **`apply_patch` 限制披露：** 在此 ZCode 运行环境中不存在字面意义上的 `apply_patch` 工具。我使用了该运行环境原生的文件编辑工具 (Edit/Write)，它们扮演着相同的角色——在四个已授权路径内进行精确替换，不对其他地方进行批量重写。未声称与 `apply_patch` 保持字节级别的兼容性。
- 没有模型/网络调用，没有安装，没有读取真实数据（使用 `tmp-dir` 下的 `SQLite` 测试数据库）。`lint` 环境说明：`ruff` 未在 `.venv` 中安装；我通过 `uvx ruff` (只读工具获取，未安装包到项目中) 运行它。工作树中其他任务预先存在的修改未受影响。

## 已执行工作

保留了先前调查的两项发现（证据见前一份报告，现已固定为永久回归测试）：(A) `fact_correction_service._reproject_expectations` 中硬编码的 `gap_signals=[]` 导致来自源运行的显式结构化 OCR 风险在更正后被静默丢弃，将 `observed_weak` 升级为 `observed`；(B) 当已到期模板失去了所有覆盖事实且没有任何信号时，同样的空信号重新投影（reprojection）抛出 `ProjectionInputError`，将合法的更正作为 `FACT_CORRECTION_APPLY_FAILED` 回滚。

按照所有者的决定实施修复：

1. **提取 (`app/services/fact_expectation_gaps.py`, 新建)：** `_expectation_gap_signals` 的主体被原样移动到 `expectation_gap_signals` 中；`_EXPECTATION_INPUT_INCOMPLETE_CODE` 现在从该模块导出一个值（执行器导入别名）。执行器保留了一个 `_expectation_gap_signals` 包装器，该包装器委托并将自身的模块全局变量（`list_expectation_templates`, `EpisodeRepository`）作为注入查找进行传递——这是必要的，因为 `test_fact_normalization_persistence.py` 中的三个现有单元测试（不可由我写入）对执行器模块上的这些名称进行了 `monkeypatch`；生产路径通过共享模块解析它们，因此行为相同。没有循环引用（该模块仅导入 `domain/storage/workflow.errors`）。
2. **源运行选择 (`select_reprojection_source_runs`)：** 活动的、未被取代的事实/事件/暴露的 `run_id` ∪ 通过迭代遍历不可变更正记录（以 `new_entity_id` 为键）可达的更正目标的运行谱系。拒绝：循环、收敛分支（由两条更正指向一个新实体）、类型不匹配的谱系链接、缺失的实体/运行以及任何权威元组不匹配（`ReprojectionLineageError`）。没有前缀/名称启发式算法，没有全历史运行收集，没有基于取代的分辨率推断，没有无界递归（迭代进行 `visited-set` 遍历）。
3. **信号重用：** 来自所选运行的持久化未解决项（已排序）+ 事务发布门结果 + 事实候选（`isinstance` 过滤）输入到共享推导中；到期模板回退（判断→`observation_unverified`，其他→`record_incomplete`）来自同一个未更改的推导。风险持续存在，除非有明确记录；未发明任何分辨率机制。
4. **保守填充 (`_prior_unreconfirmed_signals`)：** 对于在重新投影时最新的相同权威预期带有无法从所选运行重现的信号派生风险（仅信号弱缺口 `ocr_or_parse_risk`/`historical_source_unavailable`；具有 `source_coverage="complete"` 的 `observation_unverified`；非回退 ABSENT 类型；`referenced_missing`）的模板，它发出一个非回退的 `observation_unverified`，解释了先前的状态无法被源重新确认——它从不复制旧的 `gap_type/detail`，也从不重写历史行。当任何具体的非回退信号已覆盖该模板时，以及当存在通用的具体信号时，会跳过填充；回退类型的先前缺口 (`record_incomplete`/无完整覆盖的 `observation_unverified`) 从不进行填充，因此真正完整的覆盖不会被不必要的降级。`prior.authority != authority` 的预期将被忽略。
5. **未更改的保护机制：** 局部/节点范围逻辑，事务回滚，仅追加的实体/预期/更正/配置文件均已保留；`_reproject_expectations` 现在将重建的信号传入相同的投影调用，将 `ReprojectionLineageError`/`StepFailure` 包装成 `FactCorrectionError`（原子回滚）。

**测试 A 重构（按照指示）：** 它现在通过 `FactNormalizationUnresolvedItemRepository` 在源运行上持久化一个真实的 `PersistedEvidenceNormalizerUnresolvedItem`（`OCR` 风险绑定到模板的需求），并通过从持久化记录运行的共享 `expectation_gap_signals` 派生其初始的 `observed_weak` 预期——不再有注入的投影输出。两个 xfail 均已移除，仅在两个期望行为测试通过后才移除。

新测试：多步谱系（原始运行风险在两次链式更正后存活；最新预期修订版 3 保持 `observed_weak`+`ocr_or_parse_risk`），孤立历史运行排除（具有未解决项且没有活动实体/谱系引用的运行不得泄漏；预期保持 `observed`），无源关联的先前风险（通过填充保持弱状态为 `observation_unverified`，未重新断言，未清除），以及解析器循环/收敛分支防御（使用从现有 `_fact`/`_correction_for_facts` 固定装置构建的真实合同对象进行的纯函数测试）。

## 工件与证据

- `app/services/fact_expectation_gaps.py` (新建) — 单一信号推导 + 运行选择器 + 谱系追踪 + 保守填充；`ruff` 清理完毕。
- `app/services/fact_correction_service.py` — 导入 + `_reproject_expectations` 重写（`gap_signals=[]` 已移除）；其他任何内容均未动过。
- `app/services/fact_normalization_executor.py` — 已移除的函数上方的委托包装器，常量别名，导入调整（重新添加了 `EpisodeRepository`/`list_expectation_templates` 以用于可 `monkeypatch` 的接缝；移除了仅提取使用的 `GapType`/`stage_rank`）。
- `tests/v2/services/test_fact_correction_gap_reprojection.py` — 7 个测试，全部通过，没有 `xfail`：`test_correction_keeps_source_risk_recorded_on_unresolved_item`, `test_correction_uncovering_due_template_completes_with_concrete_gap`, `test_correction_lineage_reaches_original_run_across_two_corrections`, `test_reprojection_ignores_unrelated_orphan_run`, `test_prior_risk_without_source_linkage_stays_weak_as_unreconfirmed`, `test_resolver_rejects_cyclic_lineage`, `test_resolver_rejects_converging_lineage`。

## 命令与观察

- `.venv/bin/python -m pytest tests/v2/services/test_fact_correction_gap_reprojection.py tests/v2/services/test_fact_correction_job.py tests/v2/services/test_fact_normalization_persistence.py -q` → **73 个通过** (7 + 27 + 39)。现有的 27 个更正作业测试和 39 个持久化测试（终结路径，包括三个 `monkeypatch` 单元测试）均通过，未做修改。
- `uvx ruff check` 处理两个新编写/重写的文件 → **所有检查通过**。执行器和更正服务中剩余的默认规则发现是这些文件中未触及区域预先存在的样式噪声（在没有仓库 `ruff` 配置的情况下运行）；根据最小差异原则，未予处理。
- 迭代期间的重要观察：最初的跨权限测试在 `_create_run_with_call` 处失败，因为 `FactAuthorityValidator.validate` 在 `fact_authority.py:104-137` 处固定了快照范围、活动指针对和 `episode_revision` — 每个存储写入路径都会拒绝外部权限的运行/实体，因此该排除在写入时上游强制执行，如果不进行禁止的数据库绕过，则在运行时无法构造。我删除了该测试，在孤立运行测试的 `docstring` 中记录了该保证，并将解析器的每实体/每运行权限相等性检查保留为深度防御（代码审查覆盖，非运行时测试）。

## 阻碍或缺失环境

- 没有阻碍性。限制已记录：（1）此处没有字面意义上的 `apply_patch` 工具（已使用运行环境编辑工具，路径范围严格）；（2）`ruff` 不在 `venv` 中（通过 `uvx` 运行）；（3）通过真实合约无法构建运行时的外部权限固定装置 — 已在存储验证器处作为证据涵盖。

## 重运行请求或下一步

- 本轮无需重运行。建议由 Codex 进行验收：对未在允许列表中的套件（例如，`tests/v2/projections/test_evidence_expectations.py`，`test_fact_correction_service_exports.py`）进行更广泛的对等测试，以确认共享模块没有产生副作用——我更改的导出集或投影器未触及，因此预计不会出现副作用；根据任务授权，临床/监管验收仍归 Codex 所有。
