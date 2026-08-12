# Phase 0.5 实施步骤

1. 创建领域枚举、基础值对象、规则/证据/受试者/审核/行动/Job 合同。
2. 实现状态-gap Gate、Agent 权限 Gate、规则表达式结构校验和节点 rollup 纯函数。
3. 建立合同测试和历史错误族的最小合成用例。
4. 编写确定性 schema 生成器，产出 JSON Schema 和 OpenAPI 草案。
5. 创建 3 个自包含 fixture 并验证 EvidenceSpan、Patient Profile、阶段和状态。
6. 记录 4 个语义 Agent 合同及确定性 Gate 的审计边界。
7. 编写设计 token、响应式、证据查看器、键盘和中文状态词合同。
8. 编写 Phase 1 UAT 任务、指标、临时阈值和停止条件。
9. 重跑完整测试、schema 重生成差异检查和独立 checker。

## 2026-08-13 第五次复核后的检查点

- 服务端只读发布注册表与版本化审核上下文已落地，发布函数不能再用待发布对象自建信任。
- 方案确认事件、来源记录、RuleSet 完整哈希、typed Candidate 和 Fixture Fact/Span 已进入同一发布闭包。
- V2 `115 passed + 2 subtests`；默认全套 `245 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品双跑一致。
- 当前仍等待同一 Luna checker 第六次验收；任务保持 `in_progress`，Phase 1 未创建。

## 2026-08-13 第六次复核结论

- 候选 `9becd6b` 被拒绝。审核上下文、typed Candidate、RuleSet 完整哈希、Fixture Fact/Span 已关闭；发布全集仍未封闭。
- 开放 P1：Candidate/Evidence/Authority Gate 注册反查、Rollup 完整集合、Action 确定性字段、临床来源与审计实体注册闭包。
- 开放 P2：Fixture 额外未登记 Agent/Gate、文档闭包表述过早。
- 下一检查点必须新增相应对抗测试并再次复用同一 checker；任务保持 `in_progress`。

## 2026-08-13 第六次复核后的根因修复

- Candidate、Evidence、Authority、Action 与 Rollup 发布链已统一改为从只读注册表精确解析既存实体，不再只检查调用方对象能否内部自洽。
- Evidence Gate 把完整来源文件版本 payload 纳入闭包；方案完整性把完整 Authority Gate payload 纳入闭包。
- Action 的责任方、补充动作、可接受证据、到期节点、触发定位与重算范围改由规则组件、证据要求、审核节点和已发布判断确定性派生，调用方接口不再接受这些字段。
- EpisodeRollup 必须覆盖规则集全部组件、全部证据要求，并为每个已确认缺口包含唯一待办；空集合、缺件、重复项和夹带未登记对象均被拒绝。
- 新增未登记调用/候选/Gate、同 ID 来源替换、Authority Gate payload 替换、汇总缺件/重复、待办字段替换、Fixture 夹带记录等对抗测试。
- 当前验证：V2 `128 passed + 2 subtests`；默认全套 `258 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品连续两次 SHA-256 一致。
- 当前候选仍未获得独立检查者接受，任务保持 `in_progress`，Phase 1 继续冻结。

## 2026-08-13 第七次复核结论

- 候选 `ac0e982` 被同一 Luna checker 拒绝；Rollup 完整集合与 Action 确定性字段已确认关闭。
- P1 仍开放：Candidate/Evidence/Assessment 可把一整套内部自洽对象改绑到未登记方案版本；Protocol Integrity 未反查独立 ProtocolVersion 与 Manifest 完整 payload。
- P2 仍开放：Prompt ID 存在但节点可与 AgentCall 错配；Fixture 的部分顶层列表可追加完全相同 ID 的重复记录并被 set/dict 折叠；文档把本地关闭写得过早。
- 下一修复统一为两项不变量：所有受试者审核发布共享同一套已登记 Project/ProtocolVersion/RuleSet/Episode/Run/Prompt 作用域图；所有 Fixture 顶层实体在任何集合化处理前执行 ID 唯一性检查。
- 任务保持 `in_progress`，Phase 1 继续冻结；第八次复核仍只复用同一 checker。

## 2026-08-13 第七次复核后的本地候选

- 新增独立 `ProtocolDocumentVersion` 注册实体和共享审核作用域解析器；Evidence、Candidate 与 Assessment 必须共同解析到同一 Project、ProtocolVersion、RuleSet、Subject、Episode、Run、Snapshot、SourceDocument、Prompt 和 Model。
- Protocol Integrity 在任何自洽重算前先反查已登记 ProtocolVersion 与 Manifest 完整 payload；Project 内嵌方案版本必须与独立登记版本一致。
- PromptVersion 必须与 AgentCall 节点一致，结构化输出合同版本必须与候选一致。
- Fixture 的 19 类顶层/嵌套实体列表在 set/dict 归一化前统一检查 ID 唯一性。
- 新增跨未登记方案版本、Prompt 节点错配、ProtocolVersion/Manifest 替换及完全重复记录对抗测试。
- 本地验证：V2 `132 passed + 2 subtests`；默认全套 `262 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品连续两次 SHA-256 一致。
- 上述仅为本地候选证据，状态继续 `in_progress`，等待同一 checker 第八次复核。

## 2026-08-13 第八次复核结论

- 候选 `6bfba2c` 被同一 checker 拒绝；第七次的跨方案 scope、ProtocolVersion/Manifest、Prompt 节点、Fixture 重复实体和文档状态五类 finding 均确认关闭。
- 新 P1：共享审核作用域只比较来源 ID 集合，未拒绝当前筛选节点读取基线来源；Fixture 路径有阶段检查，直接 Candidate/Evidence/Assessment 发布路径没有。
- 新 P2：EvidenceSnapshot 来源引用和 AgentCall Gate 引用允许重复；set 比较会掩盖 Snapshot 重复，Agent 发布未强制引用列表唯一且恰好一个结构化输出 Gate。
- 下一候选只在共享 scope 根因层修复，不进入 Phase 1；第九次仍复用同一 checker。

## 2026-08-13 第八次复核后的本地候选

- 共享 scope 现在按预筛、筛选、导入/洗脱、基线顺序拒绝未来节点来源文件，直接 Candidate、Evidence 和 FinalAssessment 发布统一生效。
- EvidenceSnapshot 来源引用、AgentCall 来源引用和 Gate 引用均强制唯一；AgentCall 必须且只能绑定一个结构化输出 Gate。Fixture 路径在集合化前也显式执行相同检查。
- 新增直接发布与完整 Fixture 的未来来源、重复 Snapshot 来源、重复 Gate 引用负例。
- 本地验证：V2 `135 passed + 2 subtests`；默认全套 `265 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品双跑一致。
- 状态保持 `in_progress`，以上不代表独立验收通过。

## 2026-08-13 第九次复核结论

- 候选 `e12b88e` 被拒绝；第八次的未来阶段来源、重复 Snapshot 来源、重复 Agent Gate/Source、零个或多个结构化输出 Gate 及相邻阶段边界均确认关闭。
- 唯一 P2：直接发布只验证唯一 Schema Gate，未逐一验证 AgentCall 另外声明的 Gate；Fixture 会验证全部声明 Gate，形成合同漂移。
- 下一候选在共享 scope 中逐一核对全部声明 Gate 的接受状态、AgentCall 引用、作用域、版本映射与输出哈希。任务保持 `in_progress`。

## 2026-08-13 第九次复核后的本地候选

- 共享 scope 逐一验证 AgentCall 声明的每个 GateResult：必须 accepted、输入和接受引用均包含当前调用、作用域哈希/版本映射/输出哈希与调用一致。
- 新增额外 rejected Gate、表面 accepted 但 scope 错配 Gate 的 Evidence 发布负例，以及 FinalAssessment 夹带 rejected Gate 负例。
- 本地验证：V2 `137 passed + 2 subtests`；默认全套 `267 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品双跑一致。
- 状态仍为 `in_progress`，等待同一 checker 第十次复核。

## 2026-08-13 第十次复核结论

- 候选 `a249d9a` 被拒绝；直接 Evidence、Candidate、FinalAssessment 对 rejected Gate 和五类错配 accepted Gate 均确认关闭，多个合法非 Schema Gate 仍可正常接受。
- 唯一 P2：Fixture 对未参与下游发布的额外 AgentCall 仍使用较弱手写检查，没有核对额外 Gate 的 input scope 和 revision map。
- 根因是同一 Gate 闭包在 Fixture 与直接发布维护两份实现。下一候选让 Fixture 每个 AgentCall 都复用共享 scope 校验器。状态保持 `in_progress`。

## 2026-08-13 第十次复核后的本地候选

- Fixture 对每个 AgentCall 无条件调用共享审核作用域与 Gate 闭包校验器，不再取决于该调用是否被 Evidence/Assessment 下游使用。
- 新增“未参与发布的额外 AgentCall + 合法 Schema Gate + scope/revision 错配 accepted 非 Schema Gate”负例。
- 本地验证：V2 `138 passed + 2 subtests`；默认 `268 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；生成制品双跑一致。
- 状态保持 `in_progress`，等待同一 checker 第十一次复核。

## 2026-08-13 第十一次复核结论

- 候选 `1535304` 被拒绝；未参与下游发布的 AgentCall 已确认执行完整共享闭包。
- 唯一 P2：Fixture 可追加一个已登记但不被任何 AgentCall、方案、Assessment、Action 或 Rollup 引用的孤立 GateResult。
- 下一候选按方案验收、AgentCall、Assessment 发布链、Action 和 Rollup 建立显式 Gate 归属集合，任何无业务归属 Gate 均拒绝；仅被其他 Gate 自由引用不能取得归属，历史审计 Gate 不混入当前发布集合。状态保持 `in_progress`。

## 2026-08-13 第十一次复核后的本地候选

- Fixture 中每个 GateResult 必须明确归属于方案权威/完整性验收、AgentCall 声明、Assessment 候选/证据/最终发布、Action 或 EpisodeRollup；已登记但无发布对象归属的 Gate 及孤立 Gate 子图均被拒绝。
- 归属不从 Gate 的自由 `input_entity_refs` 推导，避免把孤立 Gate ID 塞入合法 Gate 后伪造“图可达”。
- 新增单个孤立 Gate、两个 Gate 互相引用的孤立子图、以及合法 Schema Gate 引用孤立 Gate 三类反向测试。
- 本地验证：V2 `139 passed + 2 subtests`；默认 `269 passed, 1 skipped + 18 subtests`；legacy `130 passed, 1 skipped`；8 个生成制品双跑一致，`compileall`、`uv lock --check`、`git diff --check` 通过。
- 状态保持 `in_progress`，等待同一 checker 第十二次复核。
