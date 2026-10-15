# Conference Output: r05-frequency-consumption-20260916 - evidence_single_object

## Output

**续会声明**：同角色 fallback（`zcode`/`GLM-5.3-Flash`，effort max），只读边界同前。本轮完整读取：`repeat_acquisition_chains.py`（35 行全读）、`repeat_series_constraints.py`（162 行全读，v3）、`repeat_result_resolution.py`（227 行全读）、`repeat_observation_count.py`（与首轮读过的版本一致，无变更）、`observation_relation_graph.py`（与首轮一致，无变更）、`repeat_review_presentation.py` 呈现段。

---

### 结论：未发现可行动缺陷

**逐项核验（evidence，file:line）**：

1. **链分解只用显式关系**（`repeat_acquisition_chains.py`）：图哈希钉死（6-7）；结构原因早退（9-11）；非 initial 组的祖先闭包须恰含一个 initial 根，否则 `repeat_initial_correspondence_unverified`（28-30）——**一条 repeat 溯及两条初查不会被摊平到任一链**；自环由 `target in ancestors` 双保险（29，图分析器 CycleError 亦先行拦截）；无初查→`repeat_initial_scope_unverified`（32-33）。日期从未参与建边 ✓。
2. **每初查计数独立、留痕、消费前重算**：约束层逐链 `evaluate_repeat_count`（`repeat_series_constraints.py:56-66`，scope_complete=全局供给完备∧角色完备，保守不细化）；结果随 `acquisition_chains`+`count_by_initial` 存入 v3 约束（153）；解析层对封存图**独立重推** chains 与 expected_counts 并逐字段比对，不一致 raise（`repeat_result_resolution.py:117-132`）——变异/陈旧计数在消费前被拒 ✓。多初查时全局 `count_result` 仍 `repeat_count_scope_unverified`（94），链级计数只作逐 repeat 的 count 操作数（154-157），**计数检查≠结果采用** ✓。
3. **无虚假采用、无丢失**：链计数 FALSE 只转化为该 repeat 检查 `does_not_meet_requirements`→`repeat_execution_nonconforming` 原因→`chosen=[]`→原子 UNKNOWN（191-199），保留全部证据而不宣称原子真值；链 TRUE 在 scope 不完备时不可得（`evaluate_repeat_count` 未变：部分集只证超上限）✓。多初查结果采用维持 unknown（178-179→selection None→199）✓。per-node 计数路径（80-90）与 per-initial 分立未混用 ✓。
4. **owner 变量遮蔽已修**：解析层 `owners` 集合与循环内 `owner` 身份分离（87-92），条件字典以行级 owner 键入（35-37），无交叉污染 ✓。
5. **旧 v2 兼容**：约束版本 v2|v3 双读（105）；v3-only 的链重推/逐初查操作数/count_scope 附加字段（117, 154, 218-220）；v2 解析身份不变 ✓。
6. **哈希与完备证据**：分解钉 graph_sha256；期限检查逐 repeat 不重不漏（113-116）；`count_scope.complete` 与逐链 `scope_complete` 留痕（129, 215）；`replacement_authorized=False` 恒定 ✓。

**覆盖限制（如实声明）**：(a) 链级归组在呈现层通过逐 repeat 的 count 操作数间接可见（每条复查的“复查次数是否符合要求”即其所属链结果），`count_by_initial`/`acquisition_chains` 保留在 resolution/API 载荷但无单独链级叙述——证据未丢失，叙述粒度可留待呈现评审；(b) `repeat_observation_time.py` 未列入本增量变更、未重读；(c) 前端对新 count_scope 字段的渲染未核（视觉验收归 Codex）；(d) 按指示未运行任何测试/运行时。

**非声明**：本审阅不构成方法批准、临床接受或多初查政策的设计定案（链间组合仍待来源声明，见前轮 §4 建议）。会话保持可续。
