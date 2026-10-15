# 执行输出：fact-correction-gap-replay-20260910 - worker_01 (残留缺陷修复轮次)

## 边界与上下文检查

- 范围与 `provenance-repair.md` 相同：仅涉及九个授权文件；本轮仅修改了 `app/services/fact_expectation_gaps.py` 和 `tests/v2/services/test_fact_correction_gap_reprojection.py`。无网络、无 `uvx`、无安装、无模型调用、无委托；无真实数据（使用临时 `SQLite`）。工具限制未变：此运行时中不存在 `apply_patch` 工具； edits 使用了运行时原生编辑器，未声明替代方案等效。

## 已执行的工作

**修复 1 — 填充抑制现在使用精确的输入来源覆盖率 (`_prior_unreconfirmed_signals`)。** 移除了全局具体信号提前返回，以及按模板的“任何具体信号存在”跳过。对于每个到期的模板，仅在以下情况下跳过填充：先前的状态为 `observed`/`not_due`，或者为纯源强度弱（`observed_weak`+`provenance_followup`），或者先前的 `input_gap_signals` 为 `[]`/仅回退（明确已知的），或者——针对新的覆盖率规则——先前的每一个具体的适用信号（作用域为 `applies_to_template_id in (None, template.template_id)`）都被当前的适用具体信号集**通过规范化的结构化五字段等价性**（kind/detail/referenced_file_id/template binding/fallback_only, `canonical_hash(model_dump)` 键——无类型匹配，无细节子字符串匹配）所重现。任何未重现的先前具体信号，或旧版 `None` 的来源，无论存在哪些新的具体信号，都会触发非回退的 `observation_unverified` 填充，其细节引用了先前的相同权威期望 ID。缺失重现从未被解释为解析。观察到的/未到期的以及纯源强度的排除项按授权予以保留。

**修复 2 — `UNVERIFIABLE` 事实不能抑制被拒绝的候选者风险。** 按要求预先验证：`SourceStrength.UNVERIFIABLE = "unverifiable_source"` (`enums.py:815`)，且 `project_expectations` 的 `_coverage_verdict` 返回 `"none"` 用于 `UNVERIFIABLE` 事实 (`evidence_expectations.py:165-166`) — 它们绝不是覆盖。`reconstruct_reprojection_gap_signals` 现在在构建 `accepted_requirements` 覆盖时排除 `UNVERIFIABLE` 活跃事实；终结器的 `None` 路径未受影响（基于门控的推导保持不变）。

## 工件与证据

新增五个集成测试（实际种子链、实际存储库、实际执行器——无猴子补丁）：

1. `test_prior_pad_survives_unrelated_new_concrete_signal` — 先前具体的未经验证输入 + 完整事实 + 稍后出现的新具体 `DESCRIPTION_INSUFFICIENT` 未解决项 → r2 保持 `observed_weak`+`observation_unverified` 且带有链接填充（旧代码：`provenance_followup` — 不确定性被擦除）。
2. `test_same_kind_different_detail_prior_input_not_erased` — 先前注入的 OCR 风险 "A"; 源运行后添加的 OCR 未解决项 "B" → r2 保留链接填充以及 B 信号，且不包含 A（按结构 equality 而非类型匹配的覆盖率检查）。注意：模型未解决项契约禁止 `observation_unverified` (`evidence_normalizer.py:431-443`)，因此两侧均使用真实可持久化的 `ocr_or_parse_risk`。
3. `test_correction_keeps_source_risk_recorded_on_unresolved_item` (扩展) — 精确重现的先前输入（源运行项) 产生 `r2=weak+ocr` 且无填充；确切复现的细节存在于 `inputs` 中，没有“先前期望”填充细节。
4. `test_unverifiable_current_fact_cannot_erase_rejected_source_risk` — 元数据来源重写为不可验证（正式合同重编码 + 通过 `manifest_sha256_for` 重新计算完成哈希）；`UNVERIFIABLE` 事实 + 同一需求上的被拒绝候选者。终结模式 (`None`)：被拒绝的风险被抑制 → `absent`+`record_incomplete`（保留行为证明）。修正（事实类型修正，一种将局部范围重新投影带入此处的签名更改）：用旧逻辑，重投影将是与 `r1` 的无操作（`no-op`）幂等重用；用修复，`r2=absent`+`ocr_or_parse_risk` 具有特定的拒绝原因细节。
5. `test_prior_pad_ignores_expectation_from_other_authority` (“如果实际可行” — 实际可行)：种子 → 具体输入的弱预期在 `episode` `revision` 1 下持久化 → `episode` 推进到 `revision` 2（通过 `_update_episode`） → 新的权威修正 → `r2=observed`，旧的权威预期不驱动填充。

## 命令与观察

- `.venv/bin/python -m pytest <4 allowed suites> -q` → **127 个通过** (15 + 27 + 39 + 46)，包括未更改的 `correction_job` / `normalization_persistence` / 投影套件 — `finalize` 行为和所有先前的回归均完好无损。
- `py_compile` 处理已更改文件 → 正常。中间探测（内联脚本，无文件写入）验证了 `UNVERIFIABLE` 场景达到了重建级别的修复，但暴露了影响规划器的特征更改要求 — 已在测试中吸收（事实类型修正）；规划器的局部范围闭包本身未更改（不在授权的缺陷范围内）。
- 构建设置期间的固定装置限制：`unverifiable-source` 元数据路径需要完整的修订完成哈希重计算，以及元数据和有效负载镜像上的 `source_party` 列镜像 — 均通过正式编解码器完成。

## 阻碍或缺失环境

- 无阻塞。限制未变：无字面上的 `apply_patch` 工具；旧版 `None` 填充和权限排除在 `service/integration` 级别通过真正构造的状态进行了验证，而不仅仅是 `monkeypatch`；按照授权，`ruff`/`uvx` 未使用，因此已更改文件仅进行了编译检查和审查。

## 重运行请求或下一步

- 本轮无需重运行。给 Codex 的范围外观察（不采取行动，仅供注意）：影响规划器收集受影响期望的闭包基于覆盖范围/签名，因此具有相同签名的事实修正不会重新投影因覆盖为空而目前无法从源重建的预期 — 行为保持不变（无升级），但如果需要刷新，此类修正不会刷新它们。根据授权，临床验收仍归 Codex 所有。
