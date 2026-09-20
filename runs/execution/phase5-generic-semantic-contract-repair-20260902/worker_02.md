全部验证完成。以下为执行报告。

# Execution Output: phase5-generic-semantic-contract-repair-20260902 - worker_02

## Boundary And Context Check

- 工作目录绑定:`enrollment-review-app/.worktrees/phase5-clinical-facts-profile`(分支 `codex/phase5-clinical-facts-profile`)。未读写任何工作区外的生产路径；仅写入授权目标 `app/protocols/deconstruction_gate.py`,临时脚本一律放在 `/tmp`。
- 初始读取集两份文件已读：执行上下文与执行计划。执行上下文 "Source Of Truth" 为 TODO(未列具体文件)，故按工作项表述自主定位权威源：工作项指向的“确定性门禁”即方案拆解确定性发布门禁 `app/protocols/deconstruction_gate.py`(12 项检查、fail-closed 语义)，并交叉阅读了 worker_01 对应物 `app/agents/protocol_deconstructor.py` 的 `_SYSTEM_CONTRACT` 以保证门禁与提示合同一致(该合同已规定："‘性别不限’不是入组限制，不得虚构为男/女分类原子”、"只有原文出现‘或/任一/任何一项/至少一项’等替代连接语时才可拆替代分支”)。
- 未做最终临床/监管验收，未评审 peer workers(worker_01/03),未召开会议。

## Work Performed

审查发现三类通用中文表达缺陷并以最小修订修复(全部改动仅在 `app/protocols/deconstruction_gate.py`,6 处)：

**缺陷 1(假阳性)：非限制性表述被当成实质性义务。** `_substantive_obligation_segments` 的 `nonrestrictive` 正则只认“性别/种族/民族+不限”，基线实测“男女不限、不限男女、种族、民族不限、男女均可、无论男女”全部落入义务清单，会触发 `PARENT_RULE_OBLIGATION_NOT_COVERED`,且与提示合同“不得虚构男/女分类原子"冲突(合同禁止的做法恰是唯一补法)。→ 通用化为：人口学属性名词(性别|年龄|男女性|男女|两性|种族|民族|婚姻状况|婚姻|宗教信仰|宗教|职业|地域)支持顿号/和/与/及连接、前后两种语序(“X不限”/"不限X")、“无论/不论”让步式、“均可+参加/入组”尾缀。词表全部为通用人口学/结构词汇，零项目特异规则。

**缺陷 2(假阳性+fail-open 漏洞)：“之一/任一”明确替代关系不被识别。** 基线实测:`_has_unambiguous_disjunction("符合以下条件之一：…；…")` 返回 False;门禁场景中——(a) 原文明确“符合以下条件之一”而草稿正确用 ANY 时被误报 `DISJUNCTION_NOT_BOUND_TO_SOURCE`;(b) 更严重：原文写“之一”而草稿折叠成 ALL 时门禁完全沉默(fail-open,过拟合漏放)。→ 新增 `_ALTERNATIVE_LEAD_IN` 编译正则(锚定到 条件|标准|要求|情形|情况|条款|项|条|者 之一，及 以下/下列/如下/下述+之一、任选其一、一项或多项、至少一条 等；非结构用法如“最常见类型之一”实测不匹配)，接入 `_has_unambiguous_disjunction`;并在 `_branches_have_source_disjunction` 增加替代路径：原文含显式替代引导语时，分支分隔可由顿号/逗号/分号承担，但各分支仍必须逐一定名于原文(与提示合同“有显式连接语时可拆列举项”一致)。修复后：之一+ANY 正确结构通过；之一+ALL 折叠被 `DISJUNCTION_CHANGED_TO_CONJUNCTION` 拒绝(fail-open 补上)。

**缺陷 3(假阳性)：结构引导语不覆盖“之一/任一”变体。** `structural` 正则只认“所有/全部/各项”，“符合以下条件之一、满足下列标准之一、符合以下任一条件、满足以下任意一项、符合以下条件之一方可入组”均被当成义务。→ 通用化为封闭引导词表(主语+均+助动词+满足/符合/具备/达到+以下/下列/下述/如下+量词+空泛名词条件/标准/要求/情形/情况/条款+方可入组/即可/者尾缀)，并补“排除标准”标题(与已有“入选标准/除外标准”同类)。封闭词表保证临床内容词(如“满足以下缓解条件者”)无法全匹配，实质条件不吞。

**一致性小修：** `DISJUNCTION_NOT_BOUND_TO_SOURCE` 的修复指引文案同步提及“之一”。**版本义务：** `DECONSTRUCTION_GATE_VERSION` 升为 `protocol-deconstruction-gate/2026-09-02.1`(文件内注释要求改变判定语义必须升版；该常量在 `protocol_workbench_service.py`/`protocol_deconstruction_executor.py` 中仅作缓存等值比较，升版安全并会使旧检查点失效重跑)。

## Artifacts And Evidence

- 唯一修改文件:`app/protocols/deconstruction_gate.py`(工作树本就有其他未提交改动；我的增量=版本号+`_ALTERNATIVE_LEAD_IN` 常量+`_has_unambiguous_disjunction`/`_branches_have_source_disjunction` 各一处+`_substantive_obligation_segments` 正则块+一处文案)。
- 修复后行为(观察，脚本实测)：非限制性 6 例全过滤；之一/任一引导语 5 例全过滤；“符合以下条件之一：…；…" 判定为替代；之一+ANY 场景 boolean_logic 零问题；之一+ALL 场景报 `DISJUNCTION_CHANGED_TO_CONJUNCTION`。
- fail-closed 保持(观察)：实质条款(既往用药/阈值/缓解条件)仍是义务；频率词("2次或以上”)、审核节点词(“筛选或基线”)、且连接伪造 ANY 仍被拒；无引导语的顿号列举不得拆 ANY;“最常见类型之一”不触发替代；或式→ALL 弱化仍被拒。

## Commands And Observations

- `PYTHONPATH=$PWD .venv/bin/python /tmp/worker02_baseline.py`(修改前后各一次)：前=三类缺陷复现；后=全部修复。
- `PYTHONPATH=$PWD .venv/bin/python /tmp/worker02_failclosed.py`:上节 fail-closed 断言全过。
- `pytest tests/v2/protocols/test_deconstruction_gate_slice3.py -q`:**114 passed**(含 12 项检查全过、引导语/例外/伪造 ANY/或→ALL 等既有用例)。
- `pytest test_publication_service.py test_redeconstruction_backend.py test_protocol_deconstructor_adapter_slice3.py test_slice58_dnf_wire_contract.py test_parent_rule_semantic_segmentation.py test_time_constraint_calendar_units.py -q`:184 passed, **2 failed**。
- 2 个失败(`test_time_constraint_calendar_units.py::test_gate_accepts_three_months_only_when_month_unit_is_preserved` 与 `::test_gate_can_prove_four_weeks_equals_twenty_eight_days`)经受控实验(ASCII 锚点脚本 `/tmp/worker02_revert_experiment.py` 将我的全部修改逐块还原后重跑)证实**先于本会话存在**：完全还原版同样 2 failed;失败检查为 `REVIEW_STAGE_REQUIREMENT_MISSING`("随机前3个月/4周内”锚点要求基线资料要求，夹具未建)，位于我未触碰的 `_temporal_semantics`,推测系 8 月 29 日门禁时态收紧与其他未提交改动后夹具未同步。实验后文件已逐字节恢复(diff 校验一致)。
- `grep`:三个被改函数无任何外部调用方;`import app.protocols.deconstruction_gate` 正常。

## Blockers Or Missing Environment

- 无阻塞。需 Codex 注意的一处既有问题(非本工作项造成，证据见上节):`test_time_constraint_calendar_units.py` 两个发布性用例因 `REVIEW_STAGE_REQUIREMENT_MISSING` 失败，属时态/资料要求合同与夹具不同步，建议由 Codex 裁定修夹具还是修合同(与 worker_03 的新增测试工作有交集)。
- 不确定项(推断，未验证)：运行时 LLM 产出的真实草稿中“之一”引导语的实际形态分布仅以合成条款验证；worker_03 的故障注入测试将提供系统性覆盖。

## Rerun Requests Or Next Step

- 建议由 worker_03 在其新增回归中纳入本报告 "Artifacts And Evidence" 与 fail-closed 两组场景(尤其：之一+ALL 折叠必须被拒、无引导语顿号列举不得拆 ANY、“最常见类型之一”不得视为替代)，并覆盖“男女不限/性别、种族不限/无论男女”分段过滤。
- 若 Codex 认定提示合同(worker_01)应把“之一”列入其“或/任一/任何一项/至少一项”连接语清单，两侧现已对齐，可直接落字。
