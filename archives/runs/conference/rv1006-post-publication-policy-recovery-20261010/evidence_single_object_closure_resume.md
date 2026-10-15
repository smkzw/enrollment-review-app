Trellis SessionStart 上下文已加载。开始同一工作树的定向只读审阅（基线 aba90c63，源码读取上限 16 次；不执行测试、不写任何文件、不新建 Trellis 任务）。先建立符号地图。

符号地图已建立（运输层 `continue_scoped_unit_repair` 1498、`continue_session` 1517、`restore_scoped_session` 1870；选择条件 11486；测试 11580/11615/11666）。并行读取合并/恢复函数与范围推导，同时定位新 validator 组成串和 snapshot 绑定调用方。

范围推导与合并函数已核。继续读取选择条件、局部批次/调用、传输三方法、新测试与 validator 组成点。

核心结论已成形。最后补读两处关键定义：transport 普通通道的会话门（解释 missing_authority 0 物理调用），以及 runner 恢复侧 binding 的建立点。

最后一读（16/16）：枚举 transport 中哪些方法接受 snapshot 绑定，以闭合"普通通道不获得虚构历史"的边界断言。

Trellis SessionStart 上下文已加载。只读审阅完成，源码访问 16/16 用尽（未运行测试、未写文件、未新建 Trellis 任务）。以下为报告。

## 实际已读范围（16/16）

- `app/agents/protocol_control_deconstructor.py`：4880-5104（`_validate_bounded_output_repair` 4972-5056 全；`_merge_scoped_unit_repair` 5059-5086 全；`_restore_bounded_wire_repair` 头 5089-5104；其闭包分支 5300-5360 沿用本会话上一轮已读实际定义，本轮 grep 复核行号未变）；7380-7544（resume 入口：7460-7495 pending-author 绑定与互斥门、7496-7523 resume_wire 可选绑定）；10770-10944（错误→范围：10722-10757 闭包键与 authority escape、10787 并入 repair_scope_unknown、10790-10851 授权赋值、10852-10884 复数闭包展开）；11470-11554（选择条件 11486-11491、prompt 组装 11492-11541）；11608-11712（local_batch 11624-11650、local_wire 与提示 11651-11667、调用 11668-11670）。停止块 11281-11327 与失败标志 10494-10496 为上轮本会话已读实际定义，本轮 grep 复核原文（11278/11283/11298/11314）。
- `app/agents/protocol_control_agent_transport.py`：1475-1515（`continue_scoped_unit_repair` 1498-1515）、1517-1549（`continue_session`）、1551-1578、1581-1612（`continue_candidate`）、1614-1665、1852-1918（`restore_history` 尾、`restore_scoped_session` 1870-1883）；并以 grep 枚举 `_scoped_resume_contexts` 全部使用点（499、1504、1716、1745、1776、1799、1822、1880-1883）。
- `app/services/protocol_control_execution.py`：2080-2144（成分清单片段含新串 2120；`_same_deep_components_with_current_gate` 2130-2144）。`output_validator=lambda: _validate_deep_batch_output`（4503）为上轮本会话已读。
- `tests/v2/protocols/test_slice58c_control_deconstructor.py`：11570-11824（旧 scoped-unit 族 11579-11662；新 `test_pending_publication_closure_uses_real_scoped_transport_not_missing_history` 11665-11722）。
- 仅 grep 证据（未读全定义）：composition 串全仓定位（含 service test 7043 断言）、`restore_scoped_session` 调用方。

## 逐挑战结论

**1）闭包授权未被扩大。** selection 的唯一改动是 11488 增 `or allow_source_closure_rewrite`；授权生产者不变：closure union 必须 ⊆ `error.structure_unit_ids`（10751-10757），否则并入 `repair_scope_unknown`（10787）→ 不建立基线/授权（10790 跳过）→ 停止（11299）。且 scoped 回复面比原 `continue_session` 通道更窄：dispositions 精确等于 union（5066）、候选来源 ⊆ union（5067-5068）、跨闭包原候选拒绝（5073-5079）、丢单元仅在 post-enrollment 且逐单元显式 `POST_TREATMENT_EXECUTION`+notes 时放行（5347-5353）。`mutable_structure_unit_ids` 可含无候选的权威单元（10844-10851），但合并只 splice union 单元、其余逐字段取自 previous（5080-5086），可改面未扩大。

**2）两种闭包模式实际兼容。** 两层校验都把二者折叠为 `closure_rewrite`（4986、5109）；授权赋值同分支（10794-10803、10846-10851）；scoped 合并对 union 内重分区与最小编辑等价成立；旧族测试对两个 authority 参数走同一消费者（11612-11614）。差异仅在 repartition 另有 `output is None` 的闭包扩展分支（10852-10884），closure 修复不需要（其触发错误来自 publication 阶段，output 非空）。未发现不兼容。

**3）只读 context 未变成可改 owned。** owned=union（11626-11627），其余 owned 全部转入 context（11628-11629）；六个逐单元映射表与两个 id 列表过滤（11638-11649）；local_wire 只含 union 处置与完全内含候选（11651-11656）；prompt 明示 context 只读（11661）。强制不靠提示：由第 1 点的合并/恢复条件兜底。残留：未枚举 batch 模型其余逐单元字段，仅提示面低风险。

**4）未知候选/跨来源/丢要求均被拒。** extra/missing→5065-5066；cross-source→5067-5068 与 5073-5079；dropped→5347-5353（测试 11601-11605 证明"改为支持说明即删除"被拒）；新测试 `sibling_source` 在运行级覆盖（11721-11722）。另注：闭包键 fixpoint 展开（10731-10744）使"相交即全含"，5073 检查结构上恒过，属冗余安全网。

**5）混合禁止清单/缺来源尾句仍被正确拒绝——结构上维持，但未复验。** scoped 合并后仍走原 restore→hydrate→`_validate_bounded_output_repair`→output_validator（生产接线 execution.py:4503）→发布门；增量未触碰门禁与 prompt 清单条件（11519-11541 的 `ENROLLMENT_PROHIBITION_UNCOVERED` 条件未变）。反证见下：新测试 inventory 全空、拒绝信息为合成，未实测这两类拒绝；相关 gate 本体本轮未重读。

**6）局部非法回答不退整批。** `bad_json`：`_parse_repartition_with_checked_time` 失败→10493 捕获→`failed_scoped_unit_repair=True`（10495）、ids 清空（10496）→停止（11283）→需要核对，回执附"不得退回整组改写"（11309-11312 区，测试 11722 断言）；`sibling_source`：REPAIR_SCOPE_ESCAPE 被 11297 或 failed 标志停止。二者均被 11396-11416 的 `not allow_source_closure_rewrite` 排除出候选/整批/continue_session。

**7）测试异常未被 fake 兜底。** 新测试只覆写 `_complete`（物理边界，11680-11682），真实 transport 的会话门（1504）、响应格式（1506）、单条 user 消息（1507）全部实跑；请求计数只在 `_complete` 记账，`missing_authority`/`budget` 断言 0 物理请求（11703），任何通道穿透即破；`_histories=={}` 与 binding 集合（11701-11702）直接钉住"无虚构历史"。旧族 fake 的 `pytest.fail` 若被吞会退化为需要核对，valid 分支的"已解析"断言（11660）仍可检出回归。

**8）末消费者实经（控制流层面）。** fault None：seen==2（11712），merge→restore→hydrate→validator 全链真实执行；但该测试 validator 为注入闭包，**未调用真实 `validate_protocol_control_batch_candidates`**；生产接线 4503 未变。故"validator 槽被二次消费"成立，"真实发布门接受该修复"仅由接线与门禁未变推断。

## 可达缺陷与最小建议

在读取范围内**无已证实缺陷**（程序边界成立）。四点残留：

- **R1（防线位置）**：普通通道对 snapshot-only 会话的拒绝在 transport 层（`continue_candidate` 1593-1595、`continue_session` 1525-1530 仅查 `_histories`；接受 binding 的仅六个字段级方法 1504/1716/1745/1776/1799/1822）。`missing_authority` 场景 runner 仍会选 candidate_only 并发出 `continue_candidate`，被 transport 拒绝（0 物理调用→需要核对，测试绿色即证无效）。最小建议：集中窗口加一条断言，把该场景末条 attempt 固定为"缺会话"型 transport_failed，防止未来某普通方法把 `_scoped_resume_contexts` 加入门。不改运行时逻辑。
- **R2（标记语义）**：binding 是 64-hex 上下文标记，transport 不比对其与 prompt；hash 由 runner 在 7476-7480 以 batch+source+pending_author_wire 计算。建议保持仅由 runner 调用 `restore_scoped_session`（现状），不把它当独立授权面暴露。
- **R3（覆盖缺口）**：新测试未含"闭包修复通过后残留第二错误（真实案例如 `RECOMMENDED_MODALITY_UNSUPPORTED`）再入后续通道"的多轮断言，且未调用真实门禁。若窗口预算允许，值得一例多轮+rfc；不需改门。
- **R4（收紧非回归）**：merge 要求 dispositions 精确等于 union（5066），模型返回子集即整轮停止（fail-closed）。原 closure 路径无 scoped 通道，故不算回归；提示层须保证模型能返回完整 owned 处置（现 prompt 11657-11667 + schema 1506 已满足）。

## 反证（可推翻上述结论的未读证据）

- 未读 `_parse_repartition_with_checked_time` 本体；若其对 patch 有额外时间/结构拒绝逻辑，第 6 点的"经其失败"语义需补证。
- 未读 `protocol_control_batch_response_format`；owned enum 裁剪证据来自测试断言（11708-11709）。
- 未 diff `aba90c63`（禁 shell）；"增量仅选择一行+composition 一行+测试"依任务陈述与代码内实证。若服务侧另有采用/身份改动，不在本次范围；已读的 `_same_deep_components_with_current_gate`（2130-2144）仅允许 `validator_version` 差异。
- 未读 service 侧 pending-author 恢复调用全文；仅确认 composition 串（2120）及其 service 测试断言（7043）。

## 局限

以上全部为控制流/授权边界证据：只证明"程序与上下文分离"后的通道选择、冻结、拒绝与停止序，**不证明模型下一条回答的正确性**；同模型家族不构成独立金标。未运行测试（集中窗口进行中，不声称通过）；未接触临床原文、原答、env/数据库。不批准临床含义。

集中窗口是否已包含"闭包修复成功后残留第二错误再入后续通道"（如先 `ENROLLMENT_PROHIBITION_UNCOVERED`、后 `RECOMMENDED_MODALITY_UNSUPPORTED`）的多轮用例？若未包含，本报告只能确证单轮闭包接续的边界。
