Trellis SessionStart 上下文已加载。本次为 C03 只读审阅，不创建 Trellis 任务、不改动任何文件。先做两处有界定位：读未提交差异范围与相关符号位置。

Bash 权限在当前非交互模式不可用，`git diff` 不可行；按窗口约束转为纯 Read/Grep 的有界读取。先定位 app 内四个受影响定义与测试落点。

定位到改动面：四个 app 模块为 `protocol_control_source_interpretation.py`、`protocol_control_deconstructor.py`、`protocol_control_candidate_alignment.py`、`procedure_catalog.py`（另含 `services/protocol_control_execution.py` 的 `_deep_component_identity`）。再定位失败码的产生点和 native_visit 测试家族。

核心文件已全部定位。开始按窗口预算有界读取四份 app 定义（并行）。

核心证明、覆盖选择、alignment 校验与列范围解析已读。补读失败判定链、native_visit 测试家族与服务侧身份实现。

关键链已基本闭合：coverage 现在为 native 行填充 `action_candidate_indexes`（deconstructor.py:4482-4495），失败码在 deconstructor.py:9320-9381 只会把「待插入且已有候选字面引用」转为语义核对失败，属封闭失败。还差一处：native 行是否真的进入 `temporal_unresolved_indexes`/alignment 选择。定位其调用点。

最后一处核验：对齐版本常量是否随本改动升级（决定非表格旧 proof 能否被跨变更复用），以及 `temporal_unresolved_indexes` 的填充位置。

## C03 独立只读工程审阅（基线 5876dea9，未提交变更面：4 个 app 模块 + native_visit 测试家族）

**结论。** 按我读到的定义：错误列、缺源、多列、部分范围、额外时间、标记脚注、未决/例外、额外节点、异 stage、部分动作，均在 `native_schedule_visit_scope_is_preserved`（source_interpretation.py:2368-2434；来源逐格相等 2392-2409、唯一节点 2410-2412、stage 来源集合相等 2413-2425）逐项拒绝；证明成立后 coverage 仍为 `candidate_linked`、`candidate_indexes` 保持空（deconstructor.py:4478-4495、4580、4610-4617），只有 alignment 逐项 `fully_expressed` 才改写为 `semantically_aligned`（deconstructor.py:9126-9136）。未发现凭该证明直接宣布 expressed 的机械路径。旧 proof 复用受 `_alignment_input_identity`（statement/unit/context_units/bound stages + `native_visit_correspondence:v1` + 候选与政策版本，candidate_alignment.py:312-337）及复用前逐条当前源码重校约束（367-405），上下文变更失效有断言。资料限制：机械层只拒“候选已声明但未核对/不一致”（408-457）；源侧新增限制无独立机械比对。语义核对接线：单候选行已接通（coverage 填 `action_candidate_indexes` → deconstructor.py:9059-9066 建对 → 9084 调用）；同行 ≥2 候选时 `len(...)==1` 不建对，仍未接。

**必须修（可复核）**
1. 校正回环与证明判据不一致，可能使同一失败重演：`native_schedule_time_excerpt_is_grounded`（source_interpretation.py:335-357）接受“完整有源列标题片段/单层标题格文字”，而接线证明要求 `scope_quote` 与合并 `header_text` 逐字相等且 time_words/affected_stage 全含（2386-2390）。若模型按提示词“或完整有源列标题”给出单层或不同分隔的合规文字，证明恒假 → 不填 action_candidate_indexes → 不建对 → deconstructor.py:9323-9381 原码失败。修：把回环验收对齐证明判据，或证明接受该列全部有源标题片段的规范拼接。
2. 多候选未接（deconstructor.py:9064 `len(...)==1`）：同行出现第二个 action 候选（4472-4495 循环累加）即跳过语义核对、仍以同一码失败。若冻结批次可能出现该形态则必须修；否则应在回交材料标为已确认残余形态。

**建议**
1. source_interpretation.py:2403-2405 未校验 `member_source_span_ids` 长度，越界为 IndexError（技术失败、非误判）；在冻结校验层补长度约束。
2. `native_schedule_scope_requires_recheck` 多列要求 all(grounded)（:328-332），与证明 len==1（:2382）判据不同，建议注释二者关系，避免把 recheck 选择误当已核。
3. 确认 `SOURCE_CANDIDATE_ALIGNMENT_VERSION=…/v8`（candidate_alignment.py:18）是否与本变更同批定版；若非表格单元的提示词/校验语义已变而未升版，其旧 proof 在输入不变时仍可复用（复用会重校，但不会重问模型）。

**残余（单列、不阻塞）**
1. 源侧新增资料限制与列外脚注含义无机械比对，模型回显候选政策即可过校验；与“不声称消费全部脚注”一致，但不得把 `semantically_aligned` 当临床忠实。
2. 唯一标记列判断依赖冻结 context 已捕获该行全部标记格（procedure_catalog.py:821-826）；若同行另一标记格因分包/多块留在别处，唯一性基于不完整集合（数据层）。
3. 自洽而错误的冻结表数据可整链通过——证明的是内部一致性，不是表本身正确。
4. 单次产品跑（16/17 组、3 调用 152.314 秒）与合成窄窗均不代表相连窗口/真实临床通过；测试仅作断言范围阅读（tests/v2/protocols/test_slice58c_control_deconstructor.py:6678-6808），不作验收。

**证据边界与替代解释。** 只读；仅读上述定义、服务身份/版本行（protocol_control_execution.py:1989-2061，validator_version 已含 `native-table-visit-correspondence/v1`）；Bash 被拒无法 git diff，“新增/既有”归属依据 Owner 摘要而非我核对。替代解释：组 17 失败也可能是真实未决——该行资料种类/脚注关系本未核清，正确动作是停止回交；本改动把“插入失败”转为“语义核对请求”，若模型未消费列外脚注即答 fully_expressed，窗口会把它推进为 `semantically_aligned`；机制上不能排除，因为源侧资料限制比对不在 validator 内。
