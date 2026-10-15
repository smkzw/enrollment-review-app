# 0929V1｜本执行包的依据与证据边界

## 编制依据

| ID | 依据 | 本包采用的范围 |
|---|---|---|
| D-R1 | 用户在0927V1后认可宏观边界，并要求同步PRD/PLAN | 完整覆盖、混合执行、例外驱动已经批准，不重问 |
| D-0929-01 | 用户在0929V1后认可B有限验证，并要求规范handoff | 新增局部原图核实试验与交接规则；不是实验已成功 |
| S-01 | `a1cf890...` 当前PRD、design、plan、acceptance | R1现行规范与继承的核心功能/安全边界 |
| S-02 | `HANDOFF_20260929_R1_PAUSE_AND_REVIEW.md` | 作者报告本机改动、308项测试及deep2结果；未作为本包独立验收 |
| S-03 | 上一轮0929V1对同提交的源码审阅 | calculation_gaps返回不一致、全包计算阻断、表格表示和诊断问题；接续先核本机是否已修 |
| S-04 | 用户上传的0927 EX-02交接 | HTTP200、局部修改及阻断数下降不证明含义正确；只作为历史反例 |

当前GitHub分支核对仍指向 `a1cf89028b9ef63aa725f5016d3f3fc2c7ab6b61`（本包编制时）。现场前移则按差异核实，不强制检出基线。

## 固定源码/文档导航

仓库：`https://github.com/smkzw/enrollment-review-app`。
基线树：`https://github.com/smkzw/enrollment-review-app/tree/a1cf89028b9ef63aa725f5016d3f3fc2c7ab6b61`。

重点路径：
- `.trellis/tasks/09-11-e2e-eligibility-review/prd.md`
- `.trellis/tasks/09-11-e2e-eligibility-review/design.md`
- `.trellis/tasks/09-11-e2e-eligibility-review/plan.md`
- `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260929_R1_PAUSE_AND_REVIEW.md`
- `app/api/v2/protocol_control.py`
- `app/services/protocol_control_status.py`
- `app/services/protocol_control_catalog_publication.py`
- `app/protocols/procedure_catalog.py`
- `app/agents/protocol_control_source_interpretation.py`

本轮重新核对分支与现行设计，读取R1计划/验收；没有重新做全仓code review。上轮具体代码结论属于同提交审阅，不能假称本轮再独立运行了这些产品测试。

## 本次做了什么／没有做什么

做了：将批准决定写为执行规范；形成两线接续、有限实验、验收、文档增量同步及handoff规则；生成并检查包内文件、链接、JSON与轻量索引检查器。

没有做：修改远端或本机产品仓库、安装文档覆盖、恢复作业、调用实际模型、访问用户临床数据库、读取本机未推送源码、运行产品pytest／HTTP／浏览器、验证临床原件或完成R1运行时迁移。

包内 `validation/` 只包含**本包工具和材料检查**，不得并入产品测试或临床验收统计。模板字段为空表示待填，不能从示例推断真实运行状态。
