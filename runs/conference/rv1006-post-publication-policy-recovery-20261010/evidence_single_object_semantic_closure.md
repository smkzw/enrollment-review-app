Trellis SessionStart 上下文已加载。开始定向只读复核（基础 bfc0f68b 未提交差异；不派工、不运行模型/服务；git diff 仅限所列三文件）。先取冻结差异与目标符号。

Bash 被权限策略拒绝（非交互模式），git diff 无法执行——改为直接读取实际定义，并与本会话早前轮次已读的旧基线做对照（此限制将写入报告）。并行读取修复函数、cited_unexpressed 分支、测试族与组成身份。

核心定义与两族测试已读出（修复函数 5107-5142、分支 10280-10370、新测试 14603-14701、scoped 族 11579-11662、组成标识 2125）。补三处决定性证据：绑定证明消费者、测试夹具来源、服务侧是否有跨运行一次性标记。

补最后两处决定性证据：分支上下文（unresolved_units/shared_candidate 的定义与顺序）与一次性标记是否跨运行持久化。

Trellis SessionStart 上下文已加载。定向只读复核完成（12/12 次读取用尽；git diff 因非交互权限被拒，未能执行；未跑测试/模型/服务）。以下为完整报告。

## 一、读取范围与方法限制

已读（12/12）：
- `app/agents/protocol_control_deconstructor.py`：5107-5142（`_reviewed_semantic_closure_repair` 全文）、5077-5104（`_merge_scoped_unit_repair` 全文）、5145-5165（`_restore_bounded_wire_repair` 头与闭包折叠）、10220-10370（`cited_unexpressed` 分支：units/unresolved_units/shared_candidate 定义 10249-10263、预门 10344-10347、语义修复调用与一次性/预算条件 10356-10370）、10371-10407（停止回执）；grep `reviewed_semantic_repair_units` 全仓（仅 8433/10364/10367）。
- `app/agents/protocol_control_candidate_alignment.py`：581-622（`reusable_proven_alignment_items` 全文：重验 `validate_candidate_alignment`、输入身份 sha、response sha、响应重解析、唯一配对）。
- 测试：`test_slice58c_control_deconstructor.py` 14603-14701（`reviewed_semantic_closure` 两族）、14542-14600（夹具 `_two_independent_candidate_linked_alignment_material`）、11579-11662（既有 scoped_unit_repair 族）。
- `app/services/protocol_control_execution.py`：2125（新组成 `bound-negative-semantic-closure-recovery/v1`，grep；services 目录无该路径的其它引用——grep 仅此一处）。
- **未执行**：`git diff`（Bash 在非交互模式被权限策略拒绝；已改用"实际定义+测试+本会话早前旧基线已读"对照，无法列出精确变更行）。**未运行**任何测试、模型、服务、网络或写操作。

## 二、授权条件逐条核对（问题：可信绑定的 incomplete 核对是否只授权一个"来源明确、无真实疑问、无跨单元共同候选"的完整单元）

`_reviewed_semantic_closure_repair`（5107-5142）实际条件与判据（**已证明**=代码+测试直接支持）：
1. `alignment is None or not statement_indexes → None`（5116-5117）：缺绑定凭据即拒。
2. 绑定重验：`bound = reusable_proven_alignment_items(..., require_positive=False)`（5118-5120）；该消费者对**当前** batch/source/coverage/wire 逐项重验：单条 `validate_candidate_alignment`、输入身份 sha256 与 proof 记录一致、response 文本 sha、响应重解析且恰有一条与 item 相等（alignment.py 604-617）。**来源/线变动 → 证明作废 → kept 为空 → None**。测试 `unbound`（14617-14619）直接覆盖"未绑定"。
3. 负核对：`negative` 必须含 `decision=="incomplete"` 且 statement_index 在本次 cited_unexpressed 内（5121-5125）；**正核对**（`positive`，14619-14620）→ None（已证明）。
4. 完整单单元：`units`=全部 statement_index 的单元集，`len(units)!=1 → None`（5126-5127，多单元已证明）；**同单元任一 statement `unresolved` → None**（5127-5128，真正歧义已证明，`ambiguity` 14621-14622）。
5. 无跨单元共同候选：凡与单元相交的候选，其来源集必须**恰好等于 units**（集合相等，5129-5134）；共享/跨单元（`shared_source`，14623-14624）→ None（已证明）。
6. 返回错误仅携带：该单元 `structure_unit_ids`、来源集恰等于该单元的 `candidate_ids`、`allow_source_closure_rewrite=True`，不含 insert/repartition/治疗后重分类（5135-5142）；测试断言 `allow_source_closure_rewrite and not allow_source_insert`（14634）。

调用侧附加门（10280-10370，已证明）：`cited_unexpressed` 仅取"确有候选字面引用"的语句（10280-10283）；无 `alignment_failures` 才计算语义修复（10356-10360）；前置对"未决单元或共享候选"要求已核来源目标复核（10344-10347，定义见 10249-10263）；只在该单元未曾进入 `reviewed_semantic_repair_units`、scoped reader 可调用且 `max(repairs, source_repairs) < max` 时上抛（10362-10370）——**一次无新证据的重复授权在单次运行内被拒**（已证明）。

结论：**是**。进入原局部接口的授权面=一个完整来源单元 + 其来源集恰等的候选集合；缺 proof/来源变动/正核对/歧义/多单元/共享候选全部返回 None（其中六类均有对应参数化测试）。**传输失败**：对齐阶段失败有独立族（14704-14739 方向：保留 partial、不扩大）；scoped 读取失败走既有 dispatch 异常路径停止（`bad_json` 族 14683-14700 已证；scoped 传输失败的最终回执路径为**推测**，依据早前轮次已读的 dispatch 边界，本轮未重读）。

## 三、逐挑战结论

1. **授权依据是否充分**（已证明）：证明链=宿主重验的对齐凭据（输入身份+响应 sha+唯一配对）+ 负核对判定 + 单元完整性 + 无共享候选；负核对仅以错误文本形式进入修复提示（5138），不构成采用。
2. **同单元未受影响含义是否受原门保护**（已证明为"门级"、**非字段级**）：局部接口只 splice"来源集恰等于该单元"的整个候选（5077-5104）；该候选内部原子无结构冻结，保护来自合并后完整消费者的再执行（restore→hydrate→output_validator）与来源/语义/发布门。测试只断言**范围外**兄弟候选与处置原样（14697-14698、11661），未断言同单元原子级保留；这属设计边界而非回归，但"同单元未受影响含义"不能表述为字段级保留。
3. **错误 scope 是否会隐式扩大**（已证明不会）：错误只带单单元 closure 授权；`_merge_scoped_unit_repair` 要求 patch 处置集**精确等于**授权单元、候选来源 ⊆ 授权、拒绝与闭包相交但不等的前候选（5083-5097）；`escape` 测试（追加范围外处置，14681-14682）被拒；restore 闭包分支再冻结范围外候选/处置。
4. **旧 partial 恢复的再次消耗风险**（**混合：已证明 + 推测**）：`reviewed_semantic_repair_units` 是每次 `run` 内新建的局部集合（8433），全仓仅 8433/10364/10367 三处引用——**没有持久化/服务侧一次性标记**（services 仅组成串 2125；pending-author 的 `*_repairs_used` 路径不含本证据）。因此**推测**：新一次运行以 `resume_wire` 恢复同一合法 partial、且同一负核对与 cited_unexpressed 仍在时，可在新运行内再次发起一次 scoped 尝试（每次运行的单元一次性仍然成立，且受该运行预算上限约束），**不以新证据为前提**。跨运行账本完整性无法由本窗口证明；这与任务说明的"不能证明跨运行账本完整"一致。
5. **一次无改善是否停止**（已证明）：`unchanged` 回复 → `final_output is None`（14699-14701 分支），consumed 仍为一次，不采用。
6. **原负核对不能当采用**（已证明）：上抛的是校验错误而非输出（10362-10370 注释"a negative review is not adoption"）；修复经原 splice、完整 hydrate、发布门与新来源复核；回执在失败分支保留 `partial_wire=wire`（10406-10407）。

## 四、必修项与最小方案

**未发现已证明的必修缺陷**（读取范围内）。按严重度列残余：

- **R1（中，恢复语义；已证明无持久化+推测可达）**：位置 deconstructor 8433/10364-10370 + 服务保存侧。反例：运行 A 的语义闭包修复失败停止 → 保存 partial（无本标记）→ 运行 B 以同一来源与对齐证据恢复 → 再次消耗一次 scoped 尝试。最小方案（二选一，均不改门、不伪造历史）：把"已尝试单元"随运行结果/partial 保存并在恢复时注入预置集合；或明确文档化为"每次运行至多一次、按运行计费"并接受该行为。
- **R2（低，健全性；已证明代码路径）**：5140 `_candidate_ids_from_wire(wire, batch)[index]` 在身份映射失败返回 `[]` 时会 IndexError；虽被 runner 广义 except 收敛为失败停止（不越权），建议在函数内先校验映射长度、否则返回 None。反例：线到批次的候选身份映射异常时，函数以异常而非 None 退出，回执分类会落到通用输出无效。最小方案：一行长度校验。
- **R3（信息，设计边界；已证明）**：单元级授权使"来源集恰等于该单元"的整个候选可被重写，同单元原子无字段级冻结；如需同单元原子保留，属后续增量，不建议在本窗加机制。

## 五、反证、未执行与未读

- **未执行**：`git diff`（权限拒绝），无法确证"仅上述文件/仅组成串"的精确差异；未运行测试（14603-14701 的断言为已读证据，非运行证据）。
- **未读/依赖早前轮次**：`_require_resolved_source_target_review` 本体；scoped dispatch 的传输失败回执路径（本轮以同族 bad_json 与早前已读结构支撑，标注为推测）；服务 `resume_wire` 的保存/恢复集成（本轮仅 grep 到 2125）。
- 可能推翻第 2 条：若未来 restore 层新增同单元原子冻结，则"门级保护"升级为字段级；当前读取窗口无此机制。
- 反证第 4 条的方向：若服务保存记录实际内嵌 attempts 并使上游以其它证据阻止重试，则 R1 降为文档问题——本轮未见该实现（仅有组成串引用）。

## 六、局限与声明

本报告为工程边界复核：只证明所读代码的控制流/授权/冻结与测试断言，**不证明模型输出正确、不证明跨运行账本完整、不构成产品交付或临床批准**。真实运行、性能与端到端行为未由本窗执行。建议的最小方案均不关闭任何门、不伪造 history、不扩大读取。

本轮为只读复核、未创建任何 Trellis 任务；是否需要将 R1（恢复侧标记）登记为 Trellis 任务或仅以文本清单交付？
