# 1006V1｜依据、已知边界与版本

本包基于用户对1006V1复审末尾“交付冻结窗口”的明确认可。它是范围/优先级决策，不证明产品已运行或模型能力足够。

## 1. 来源表

| ID | 来源 | 本包采用什么 |
|---|---|---|
| U1 | 本对话用户“认可” | 批准交付冻结窗口；以一例工作稿及一次更正后的新结果为主交付，其他优化仅在直接阻断或错误采用风险时进入 |
| H1 | [HANDOFF_20261006_1001V1_PAUSE.md](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20261006_1001V1_PAUSE.md)；同时由用户上传完整文件 | 作者报告的运行、授权及证据边界；不视为本包独立运行验收 |
| P1 | [当前PRD](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/.trellis/tasks/09-11-e2e-eligibility-review/prd.md) | R1、1001V1、现有模型条件、用药/未记录/上传归属政策、正式自动采用边界 |
| P2 | [当前PLAN](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/.trellis/tasks/09-11-e2e-eligibility-review/plan.md) | 既有P1/P2/P3与两线约束；本窗口仅收敛执行排序，不删最终验收 |
| C1 | [初答重新核验服务](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/app/services/fact_normalization_response_recovery.py) | 优先使用已存在的同调用请求/初答核实，不能扩成历史挑答 |
| C2 | [候选分区](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/app/agents/evidence_candidate_partition.py) | 保留局部坏项与派生依赖，不以保留余项冒充完整读取 |
| C3 | [规范化修订](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/app/agents/evidence_normalizer_repair.py) | 前轮静态审阅/摘录显示局部修订仍要求整包返回；仅当它直接阻断窗口时缩小模型输出责任 |
| C4 | [受限来源采用](https://github.com/smkzw/enrollment-review-app/blob/7b3ed4f9251323b3194371764f2bcd17ad94559e/app/services/protocol_control_restricted_source.py) | 现有R1部分实现必须保留保护；正常非可执行记录需有真实消费，不简单删保护 |

GitHub分支在本包准备时核对为`7b3ed4f9251323b3194371764f2bcd17ad94559e`；产品源码提交由最新交付记录指向`8b5b4c4f75f85110dfc81ce080755b1c8457144f`。没有执行新的全仓code review或本机运行验收。接续时若HEAD前移，按实际差异核相关路径，不退回旧提交。

## 2. 运行事实只引用作者报告

H1记载：原隔离任务前6组完成、第7组失败、余7组未读，251候选、0事实发布；受控重试仍失败。现行代码对原初答只读再核验保留50事实候选/10事件/6暴露/22疑问，但仍0事实发布。P1记录25个来源点中23个单项可用、2项时期关系未证、10项短编译能力缺口。最终集中178项通过，不是完整临床链验收。

这些数字仅帮助接收者定位已有材料，不作为产品完成率、准确率或新的运行状态。全部模型原答和临床证据仍仅本机可核；完整输入、具体关系是否正确不能由这些汇总数字推断。

## 3. 最短代码检查入口

只读核当前合同和实际调用者；路径被移动时查当前真实入口，不按旧函数名猜签名：

- `fact_normalization_response_recovery.py::revalidate_saved_response`。
- `fact_normalization_executor.py`中同调用恢复、调用/汇总重放与实际持久化。
- `evidence_candidate_partition.py::recover_source_local_candidates`及其下游缺口消费。
- `evidence_normalizer_repair.py::EvidenceSourceObjectRepair`及当前Runner的响应消费。
- `protocol_control_source_interpretation.py::validate_source_target_review`与受限来源/定义消费。
- 正式工作稿、原件与更正的已有API/UI入口。

不要把这张入口表当作“以上模块全部重写”的要求。先定位D节点的首阻断，限定阅读与修改范围；已有通过代码无相关证据不重构。

## 4. 包自身不执行的内容

没有恢复暂停Goal/Job，没有真实模型调用或临床库写入，没有GitHub修改或部署，没有全仓pytest、正式前端构建、Ego浏览器验收、医学金标评估或新运行数据采集。

文件哈希/链接/ZIP检查只证明包的组成可读，不证明建议正确、实现完成、实验有效或临床可用。所有交付条件均为待执行。
