# Phase 5 分片实施计划

所有切片按顺序执行。每个切片先跑聚焦测试，再跑受影响层回归；检查者与实现者分离。任何切片发现 PRD/设计缺陷时回到规划修订，不用项目特异补丁继续推进。

## 5.0 规划冻结与基线

- [x] 记录 Phase 4 基线提交、迁移头、后端/前端基线测试和旧表只读边界。
- [x] 将会商裁决转为合同/迁移/界面测试清单。
- [x] 确认测试路线与会商路线分离；当前独立测试者固定为 Cursor CLI `auto`、Pi `cms-router/minimax-m3(high)`、Pi `opencode-go/ox-alpha-free`，首次使用均先按各自 harness 做连通性测试，不得相互替代或随意 fallback。

验证：`git diff --check`，Trellis task validate，基线测试留档。

## 5.1 合同与权威身份

- [x] 新增候选合同、发布合同、PartialDateRange、SourceStrength、AssertionBasis、DurationStatus。
- [x] 新增 `0013_clinical_facts_profile_v2` 及 v2 repositories；所有发布对象绑定不可变权威元组。
- [x] 新增 FactNormalizationRun/Call/GateResult；不依赖 ReviewRun。
- [x] 证明旧占位表不进入任何 Phase 5 repository/API。

门槛：迁移升降级、外键/唯一约束、错误活动指针、旧 snapshot、非 complete revision、跨节点引用均有失败测试。

审查证据（2026-08-23）：Slice 5.1 合同/仓储/迁移及共享仓储回归 155 项通过；历史迁移 40 项通过；`tests/v2` 全量 `1735 passed, 1 skipped, 2 subtests passed`，唯一跳过为既有 oMLX 真实探测工件缺失。

## 5.2 确定性门禁先行

- [ ] 在不调用模型的结构化候选 fixture 上实现页覆盖、定位闭包、原文哈希、极性、单位、日期、来源、重复和冲突门禁。
- [ ] 只引用 Phase 4 authenticated locator；残余定位建议走 Phase 4 真实性门禁。
- [ ] 建立逐候选接受/拒绝结果和受影响范围，关键 OCR 风险只阻断关联候选。
- [ ] 属性测试覆盖部分日期、持续状态、重复键与冲突不择优。

门槛：否认/沉默/缺页种子极性错误为 0；虚构 locator、遗漏整页、空输出、邻近句否定、跨修订引用明确失败且不生成 Profile。

## 5.3 Evidence Normalizer 与持久运行

- [ ] 编写中文原生 Normalizer system prompt 和严格 JSON schema，只输出候选与未解决项。
- [ ] 实现逻辑文档切片、超长连续页组、页清单闭合和跨文档合并。
- [ ] 接入现有 Agent transport、Job/Step/Checkpoint/Lease/Idempotency；模型配置不写入领域规则。
- [ ] 发布提交前复核活动证据元组；中断、重启、迟到回包和重复请求可恢复。

门槛：真实模型最小闭环通过；Agent 失败或空输出保留上一 Profile，无永久处理中和重复事实。

## 5.4 事实发布、索引与资料期望

- [ ] 事务发布 ClinicalFact/Event/MedicationExposure/ConflictGroup 与 locator 链接。
- [ ] 构建可重建、精确身份匹配的 FactRuleLink 双向索引。
- [ ] 从 EvidenceExpectationTemplate 投影五类覆盖状态和细分缺口原因。
- [ ] 实现较弱转述事实 + 溯源提醒的双状态，不重复报完全无证据。

门槛：同内容多来源一事实多定位；矛盾并列；索引重建前后等价；覆盖状态矩阵全通过。

## 5.5 Patient Profile API 与投影

- [ ] 实现 v2 Profile revision、13 条泳道、后端首屏突出集合和历史 revision 查询。
- [ ] 提供真实 HTTP Profile API、运行时严格解码、陈旧/生成中/失败状态。
- [ ] 提供事件、事实、冲突、期望到 Phase 4 证据查看器的 locator 深链。
- [ ] 500 事实投影性能和稳定排序测试。

门槛：Profile 不读取 fixture/旧事实，不显示 Phase 6/7 主结论或行动，所有关键事件可回源。

## 5.6 宽屏 Patient Profile 界面

- [ ] 将当前 fixture 页面接到 HTTP repository，fixture 只保留隔离测试入口。
- [ ] 首屏默认突出异常、临界、趋势、冲突、弱来源和当前缺口；“全部历时信息”展开全量。
- [ ] 显示人口学、疾病/病程、节点锚点、证据版本、生成时间和待核对数；事件时间与记录时间分开。
- [ ] 点击事实在右侧原始资料中滚动定位，只有真实 bbox 画红框；冲突并列比较。
- [ ] 使用流体 Grid/Flex/minmax，目标为最大化 1080P、2K、4K，无页面级横向滚动。

门槛：单元/组件测试、构建、Playwright 1080P/2K/4K 截图与交互检查通过；500 事实仍可用。

## 5.7 人工事实修订与增量重算

- [ ] 实现有理由的事实修订服务和最小界面；保留原候选、旧事实、定位和影响范围。
- [ ] 由 locator/文档/事实/规则索引计算局部重算；无法证明时保守扩大到节点。
- [ ] 新 revision 只标记受影响旧投影陈旧，早期节点可重放且不被后期节点覆盖。
- [ ] 服务重启、任务取消、迟到结果、重复回调和局部失败回归。

门槛：改一处定位只重算证明相关范围；旧 Profile 可按原修订完整打开；无重复发布。

## 5.8 代表病例与独立验收

- [ ] 从原始输入在隔离目录创建 D001 II 与 MG-K10-SAR III 新架构测试项目，各选资料结构不同的代表受试者。
- [ ] Codex 逐事件核对人口学、疾病历程、MH、CM/治疗、检验检查/评分、日期、冲突、弱来源和定位。
- [ ] 会商只做架构/临床逻辑挑战；测试者使用真实浏览器和系统内独立 Agent 完成端到端操作，两类证据不互相替代。
- [ ] 测试者依次使用届时用户指定路线；当前固定为 Cursor CLI `auto`、Pi `cms-router/minimax-m3(high)`、Pi `opencode-go/ox-alpha-free`，不得用执行或会商模型替代。
- [ ] 每个预期外结果定位到合同、OCR、事实门禁、投影或交互根因，修复共享机制后重跑受影响全量。

门槛：P5-AC01 至 P5-AC13 有证据清单；后端全量测试、前端全量测试/构建、三档宽屏浏览器、数据库/文件状态和代表病例人工核对通过。

## 统一验证命令

```bash
uv run pytest -q
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run e2e
python3 ./.trellis/scripts/task.py validate 08-22-phase5-clinical-facts-profile
git diff --check
```

实际实现按切片补充更小的聚焦测试命令。若本地运行时依赖需要 Codex bundled Node/Python，应使用工作区依赖路径，不用未验证的系统运行时替代。

## 回滚点

- 5.1 前：可删除未发布的 `0013` 规划实现，Phase 4 不受影响。
- 5.3 前：仅确定性 fixture/门禁，无真实模型写入。
- 5.5 前：事实已发布但 Profile API 尚未切换，旧 fixture 仍仅供测试。
- 任一后续切片：停止 Phase 5 新 Job/API，保留所有不可变 revision；不得删除 Phase 4 原始文件、OCR、校对或活动证据。
