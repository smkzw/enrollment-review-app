复核完成。以下为第十七轮报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十七轮：D1/D2 修复只读复核）

## Output

### 一、确定发现

**未发现新的确定缺陷。D1、D2 修复按声明正确落地**，逐项源码证据：

**D1（初查/复查分离）——通过**：
- **枚举全量**：`initial_reasons` 以 `observation_scope_reasons`（全部所供候选的枚举完备）为底（`qualified_observation_relation.py:174,:194`）——任何候选枚举缺口阻断。
- **逐候选已核实身份**：`:197-202` 要求每个成员的 `qualified_origins[fact_id]` 等于其按初查组推导的预期角色（初查组内→initial，否则→repeat）；未核实/不符 → `repeat_initial_scope_unverified`——未知候选可能是另一个初查，不放行 ✓。
- **初查相关争议/来源失败阻断**：`affects_initial`（`:203-205`）——same_acquisition 任一端涉初查、repeat_of 的 **left（复查位）是初查**（“把初查当复查”）；disputed（`:206-207`）与来源失败的 links（`:208-209`，按 "relationship" 键区分——origins 失败已由角色检查覆盖）均阻断。**仅复查之间、或以初查为前次（right 位）的复查链接疑问不阻断**——`affects_initial` 对 repeat_of 只查 left ✓ 与分派语义一致。
- **局部图**：仅保留初查相关边重建 `analyze_observation_relationships`（`:210-214`）——初查相关结构疑问（含初查当复查、初查-复查同次合并导致的角色冲突）进入 `initial_reasons`；复查间环/冲突不进 ✓。
- **无目标自由文字疑问保守阻断**（`:215-218`，注释明示不猜归属）✓。
- **哈希/兼容**：`initial_scope` 子字典写入 `supplied_scope`（`:219-223`）→ 原范围哈希（`scope_hash` 与 `supplied_scope_sha256`，`resolution :135` 一带、构造处 `:230`）含新键；`series_constraints` 的三重绑定（`:248-253`）按键取值不受影响、哈希同源一致。选择器新参数 `initial_scope_complete: bool | None`（`repeat_result_selection.py:24`，类型校验 `:52-53`）；retain_initial 快速路径只查初查角色+初查侧完备（`:55-58`），位于全图结构/祖先/全局范围检查之前——复查侧疑问不再清空初查；**None（旧 material 无字段，`resolution :135` 的 `.get` 链）走原保守路径**（`:59-82`）✓。观察消费 **v6**（`qualified_observation_relation.py:12`）——旧评测被 `:24-25` 拒绝，不获新方法授权 ✓。

**D2（未知与冲突区分）——通过**（`repeat_atom_calculation.py:158-171`）：
- 原件真矛盾优先：日期组内不一致 → `repeat_same_acquisition_date_conflict`（`:161-162`）；非语义值组内不一致 → value_conflict（`:163-164`）——先于 truth 判定 ✓；
- `{TRUE, FALSE} <= truths` → 保留冲突（`:164-165`）✓；
- 仅已知+UNKNOWN → 合并成员未核原因（`:166-167`）✓；
- 全已知 → ALL 聚合（全 FALSE 得已知否定，不误标未核）（`:168-171`）✓。

### 二、极低备注（非缺陷）

- `:199-202` 循环内重复 append 同一原因码——`sorted(set(...))`（`:222`）去重，无输出影响。
- 局部图每次全量重建 `analyze`（`:210-213`）——仅性能小项，无正确性影响。

### 三、保留的未完成/未知边界（与声明一致，未被本轮修复绕过或扩大）

无目标自由文字疑问仍保守阻断初查采用（结构性保留，待证据语义扩展）；未确认来源身份的候选仍整体阻断 retain_initial（保守正确）；研究者自主许可的书面判断内容消费、观察排序与复查组合、无复查时的回退语义、报告 API/UI 呈现均未实现/未知——按分派保留，不计入本轮发现。

### 四、结论

仅源码复核：D1/D2 修复在**放行边界、未知/冲突分类、哈希绑定、历史兼容（旧字段走旧路径、新方法需 v6 评测授权）**四方面与声明一致，未发现错误放行初查、错分未知与冲突、或破坏历史封存的路径。未运行任何验证——编译/推导不构成运行证据，集中测试按用户决定在完整构建后执行；本报告非临床或产品验收。
