Trellis SessionStart 上下文已加载。现在按约束执行只读工程审阅（禁止写入/shell/网络/测试执行，源码读取≤16次）。先建立符号行号地图。

符号地图已建立。现在并行读取关键区域（计数：3次已用）。

核心分流与合并函数已读出。继续读取下一轮解析/恢复消费点、观察策略数据模型、两个测试及执行服务消费点。

关键路径已基本成型。补读传输失败尾部与授权集装配、`_WireModel` 额外字段策略、以及 `_invalid_observation_policy_paths` 的单元断言（计数：12→15）。

最后一处补读：`_invalid_time_operand_paths` 的排他性（与日期通道优先级直接相关），之后为第16次读取上限，进入结论。

Trellis SessionStart 上下文已加载。只读审阅完成，源码访问 16/16 次用尽。以下为报告。

## 已读范围（16/16）

- `app/agents/protocol_control_deconstructor.py`：460-461（`_WireModel`）、727-735（`_ObservationPolicyRepair`/`Item`）、5089-5540（`_restore_bounded_wire_repair`，含 5361-5453 定向候选分支）、5559-5684（`_merge_candidate_repair_payload/_merge_candidate_repair`）、6480-6530（`_invalid_obligation_atom_path` 尾+`_invalid_observation_policy_paths` 6509-6553）、6556-6601（`_merge_observation_policy_repair_payload`）、6604-6645、6817-6851（`_invalid_time_operand_paths`）、8320-8559（循环顶部：下一轮解析优先级 8397-8404、合并链 8405-8476、恢复/水合/消费者 8484-8548）、10480-10759（异常入口+三类字段抢救，新观察抢救 10632-10639）、10940-11294（focused 循环，新提案保留 11140-11194，停止块 11281-11303）、11295-11739（路由/提示/dispatch，含 11698-11701）、11740-11759（传输失败即返回）。
- `app/services/protocol_control_execution.py`：4400-4519（Runner 调用点；`output_validator=lambda output: _validate_deep_batch_output(batch, output)` 4503；组件身份与 `validator_version` 再验证 4406-4412）。
- 测试：10393-10406（观察选择器排他性：缺失→`(("obligation",0,0),)`；混入 title→`()`）、10409-10438（`_invalid_candidate_payload` 抢救复用）、10764-10849（旧 `...keeps_field_only_followup`，10 参数）、10851-10921（新 `...preserves_proposal_and_sibling`，7 参数）、10925-10970（相邻复数日期，未变）。

## 逐挑战结论

**1）新 stop 是否阻断原已支持的其他字段恢复——基本不阻断，有一处未验证交互。**
停止块 11284-11288 显式放过三条通道：`evidence_source_types_repair_paths`、`time_operand_repair_candidate`、`observation_repair_candidate`，且三者都在 10555-10639 内先于停止检查被赋值；11302 的预算子句放过 future/calendar/scope（它们走独立计数）。实际新增阻断的是：候选回复无法本地抢救（混合/越域/越权）时的**通用整候选重写**（此前会经 11391-11399 → 11713）。唯一疑点：`candidate_repair_fields`（关系字段通道）在 11441 才计算，在停止检查之后；若一个在途关系字段回复以 `CANDIDATE_REPAIR_INVALID` 失败，新 stop 会先终止，base 可能重问该授权字段。reachability 取决于 wrapper 错误上 `error_class_codes` 是否还带 `PROCEDURE_AFFECTED_STAGE_MISMATCH`（未读 `_error_class_codes`），当前测试族无此用例，建议定向补一例。

**2）被拒提案是否越过来源/兄弟冻结——未越过，三层证据。**
(a) 抢救处来源身份逐字段相等核对（10603-10610；focused 11146-11153），禁止键 `_find_forbidden_provider_key`，并在 focused 内再做候选级模型校验（11075-11083）；(b) 合并只写授权原子的 `evaluation.observation_policy`，路径集严格相等（6566-6568）、来源编号+原文必须属于该原子自身（6581-6594）、已有值仅允许改 scope（6575-6580）；(c) 消费前 `_restore_bounded_wire_repair` 以已接受稿为基线再冻结一次（8497-8513），兄弟只有被替换索引变化。注意一个有意行为：提案的**非来源、非禁键字段被整体保留**作为后续字段修订的基稿（11164、10636）——这正是"避免重复生成未改变临床含义"的设计，临床上最终只由完整门禁赋权。

**3）额外字段/混合错误是否获授权——不获授权，但"额外"的拒绝不是 fail-closed 停止。**
- 多返回项（重复/错位）被 6566-6568 拒绝（两测试 `extra` 均 policy_calls==1 后失败）；顶层多余键受 `_WireModel`/`ContractModel` 的 extra 配置约束（未读，见局限），且写路径只落到授权原子的策略对象，不产生越界字段。
- 混合错误：两个选择器都是全有或全无（观察 6533-6543 + 单元断言 10393-10406；日期 6832-6842），混合→双双 `()`→新 stop→需要核对；`other_error`/`scope` 两测试断言 policy_calls==0。但"extra"进入的是 `OBSERVATION_REPAIR_INVALID` 链（见缺陷 A），说明字段通道不合法在一般路径上并未全部停止。

**4）通用候选路径与 focused 循环是否不同——不同，且这正是缺陷 A 的成因。**
差别：(i) 失败包容。focused 一切异常立即 `需要核对`（11205-11237）；一般路径的后续字段回复失败会回到主循环重新判定。(ii) 停靠方式。一般路径把提案存进 `repair_baseline_raw` 并利用下一轮顶部 8397-8404 的**最高优先级**观察合并（先于 future/calendar/post-treatment/evidence/types/time/candidate/全量解析）；focused 在内存 `repaired` 上完成并以 `raw_text=修复后整线`+清空状态 + `continue` 收口（11204-11243）。(iii) 选择/预算。focused 限 1< 抢救索引 ≤3、对 owned spans 做 grounded 检查（11017-11030）、每子步扣预算；一般路径仅要求单 `candidate_repair_index`，无 grounded 复查（依赖后续来源门禁）。(iv) 通道顺序两处一致：来源类型 > 日期 > 观察（10612-10639 与 11156-11176）。

**5）missing policy 填补是否被当作语义已核——不是。**
采用唯一路径：合并仅得 staging dict（"this payload is not an accepted wire"，6562）→ `parse_protocol_control_agent_wire` → `_restore_bounded_wire_repair` → `_validate_bounded_output_repair`（8539-8548）→ `hydrate` → `output_validator`（8537-8557，生产即 execution.py:4503 的真实门禁）。回执文案亦声明"整批仍须通过原发布门禁"（11117、11202）。新测试 consume 第二次被调用后才 `已解析`（10917），且 `valid`/提案对象均未被回写（10913-10914 断言）。

## 真实可达缺陷

**A（主缺陷，被夹具遮蔽）：观察字段回复被拒后仍会重问整候选。**
路径：10590-10639 抢救成功 → 11698-11701 发 `continue_observation_policies` → 下一轮 8397-8403 合并；若回复路径集/mode/selection/来源越界（6566-6594），抛 `OBSERVATION_REPAIR_INVALID`。此时：`candidate_repair_index` 为 None（观察轮在 11438 已置 None），观察/时间/来源类型抢救标志均为空 → 停止块 11281 不命中（无该码子句）→ `candidate_only`（11391-11399，`repair_candidate_indexes` 因 10551 含该候选、len==1）为真 → 11713 再次 `transport.continue_candidate`。新测试 `failure in {"source","extra"}` 即走此路：夹具 10876 的 `assert self.candidate_calls == 1` 在**传输内部**触发，被 11732-11759 的传输边界兜底转为 `transport_failed` → 测试仍绿，但"缺失字段不能触发再次整候选重写"的意图在代码上已不成立。安全性未破（未达门禁、最终 `final_output=None`），但正是本增量要消除的"重复生成"；同类结构存在于顶层其他 typed 合并失败（8419-8437 链，未逐一验证各失败码）。

**B（状态耦合，低置信）：** 停止子句只认上一轮的单个 `candidate_repair_index`，对复数/观察轮保持的 `repair_candidate_indexes` 无对应子句；`CANDIDATE_REPAIR_INVALID` 要出现必须上一轮 `candidate_repair_index` 非空（8469 条件），因此主停止在单候选链上自洽，但该不变量不是全局"禁止整候选回退"，复数链（8453-8458）未获得同等停止保护。

**C（测试口径）：** 两个测试的失败分支只断言 `final_output is None` 与 policy_calls；不区分"正确停止"与"先发起整候选/整批再被夹具断言打断"。42 passed 因此不能证明"字段通道不合法时停止、不退整包"的边界。

## 最小改动建议

1. 把观察（及结构同类的 typed 合并）失败变为终态：在停止块 11284 增加 `or (previous_observation_repair_candidate is not None and error.code == "OBSERVATION_REPAIR_INVALID")`（时间/来源类型同理各加一条，或等价地在 8397 合并 except 内直接 `需要核对` 返回，与 focused 的 fail-closed 对齐）。改动小、不动采用权限、不影响四条既有正常通道（它们在检查前已设置状态）。
2. 让测试真正钉住边界：把夹具内 assert 换成**运行后**断言（如 `assert transport.candidate_calls == 1` 于 `run()` 之后、断言最后一条 issue 含停止文案），保持消费者与门禁断言原样，不为追绿放宽任何 validator。
3. 视意图补一例关系字段回复无效的用例，明确 stop 与重问的取舍（挑战 1 的未验证交互）。

## 证据局限

- 禁止 shell/git，无法读取基础 9431f58f 实际定义；"原分支如何"依赖任务描述与代码内注释，非独立 diff 证据（例如停止块在 base 的确切形态、夹具修改内容均不可核）。
- 未读窗口：deconstructor 6646-6810、6853-7269、**8559-10480**（成功/接受路径主体与变异授权集装配，仅读了 8497-8548 消费入口）、**10760-10940**（异常分支中段）。缺陷 A 的结论基于已读停止点全集；若未读窗口存在该码的提前返回则需修正。
- execution.py 仅读 4400-4519，无法定位该文件在本增量中的实际改动点；所见 `output_validator` 仍为 `_validate_deep_batch_output`，未见新采用通道。
- `ContractModel`/`ObservationPolicy` 的 extra 配置、`parse_protocol_control_agent_wire` 对 `{"candidate_draft"}` 回复映射为 `CANDIDATE_REPAIR_INVALID` 的实现、`_error_class_codes` 未读；测试未执行（禁止），42 passed 为用户报告，未复现。
- 本结论仅为程序边界观察，不构成产品最终批准或医学批准。

是否需要为上述最小改动开一个 Trellis 任务（含定向用例），还是作为直接小修由你另行安排？
