# Phase 5.8d Package 114 生育能力定义与证据边界验收检查点

## 当前状态

- 当前不可变计划为 `papl-e17d498106b6f71f440ff2be`：1848个结构单元、1240个语义目标、131个包。
- Package114 `pap-cd76207b0f3d157c2eaa66d6` 已验收；剩余93包，`claims_complete=false`。
- 未调用临床语义模型，未发布，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。

## 来源与语义边界

- 严格拥有 `body.p1310-p1321`；仅只读附加Package115拥有的 `body.p1322`，用于闭合“绝经后女性”定义，不迁移所有权、处置或发布责任。
- p1310-p1312仅作结构；p1313-p1321作为既有IN-06及妊娠试验/FSH控制的适用人群、分支与证据方式，使用 `supporting_or_supplement`。
- p1314的p1315/p1316/p1321为OR；p1316的p1317/p1318/p1319为OR；p1320的病历核查、医学检查、病史询问为OR。p1318/p1319保留“双侧”。
- 本包没有新的独立参加研究前动作，零候选是防重复发布结论，不表示这些来源与入排无关。
- Package113题录、无主p1309及Package115的p1323-p1333均未吸收；避孕起始时间、方法、禁止项和给药后持续时间留给Package115。
- 当前处置合同不能在 `supporting_or_supplement` 上直接挂既有规则标识；本包通过known targets保留IN-06和妊娠/FSH语义背景，不伪造重复候选。仅在后续真实需求证明必要时再评估共享合同扩展。

## 工件与验证

- 配置SHA-256 `5384847d3396135d157ab5052d2618d560d341855df5768160b90eed7075a1dd`；清单SHA-256 `a3de812470ba52a3170d65b43e2a2f2822a0829d8f18d1a0d9f7926178fca3a4`；测试SHA-256 `a1e5b169785fcc2a376ee4fe5dcc6d0bf450f53a56ed91b5fbb8a88925590421`。
- 模型外准备 `12/1/13`，prompt SHA-256 `dbee48a3978d3da0d7f4e6f48011c2196c06002f41b45166cd0852e264775950`。
- 专项 `29 passed, 5 warnings`；Package103-114组合回归 `300 passed, 5 warnings`；slice59n共享回归 `39 passed, 5 warnings`。
- `worker_01-03` 完成日间 `cursor/default` 执行；`worker_04` 在新夜间会话边界由运行器记录为CodeBuddy同会话续作并以 `codebuddy-cli/deepseek-v4-flash` 完成。四个节点return code均为0，正式执行审计通过。

## 下一安全动作

从当前冻结计划审查Package115 `pap-9fb70d121e089bc533c21255` 的 `body.p1322-p1333`。先恢复完整绝经定义、避孕起始时间、方法分组、禁止项和持续时间的父子逻辑，再判断它们与既有IN-06及妊娠/FSH控制的补充或覆盖关系；不得重复发布已有控制，也不得回写Package114所有权。
