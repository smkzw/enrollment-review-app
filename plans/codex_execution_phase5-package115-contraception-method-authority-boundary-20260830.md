# Codex Execution Plan: phase5-package115-contraception-method-authority-boundary-20260830

Objective: 在D001 II期当前不可变131包计划中，完成Package115 body.p1322-p1333的绝经定义、女性避孕起始时点、持续期、允许/不可接受方法、专业判断、沟通记录与条件性联系动作的模型外语义闭环；对照既有IN-06、妊娠/FSH控制及已验收p1325/p1326代表组，保留父子AND/OR、模态和不同时间锚点，不重复发布已有控制，不回写Package114或吸收Package116 body.p1334起内容；产出最小配置、父级临床清单、确定性回归、独立攻击验收和可恢复记录，不进入临床语义模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | worker_01：只读核对Package115冻结身份、body.p1322-p1333完整原文、39项语境、Package114/116边界及既有IN-06、妊娠/FSH和p1325/p1326验收工件；重建绝经定义、时间锚点、方法分组、禁止项、建议项和动作模态，明确潜在内部锚点差异。 | `runs/execution/phase5-package115-contraception-method-authority-boundary-20260830/worker_01.md` |
| `worker_02` | worker_02：在父级补齐Source of Truth与授权路径后，仅在Package115授权路径内创建最小配置、父级临床清单和专项回归，运行模型外dry-run；复用已验收p1325/p1326语义，禁止把方法OR压为AND、建议改为强制、禁欲可靠性评估丢失或重复发布IN-06。 | `runs/execution/phase5-package115-contraception-method-authority-boundary-20260830/worker_02.md` |
| `worker_03` | worker_03：只读独立攻击Package115方案，重点检查p1324与IN-06/p1325时间锚点混淆、绝经定义断裂、方法组OR变AND、高效/可接受/不可接受类别串线、激素禁用丢失、避孕套同时使用误读、建议性妊娠检查强制化、计划访视量词缩减及Package114/116吸收。 | `runs/execution/phase5-package115-contraception-method-authority-boundary-20260830/worker_03.md` |
| `worker_04` | worker_04：待父级复核后只读验收真实工件；复跑专项、相邻包和共享语义回归及dry-run，核对所有权、父子逻辑、时间锚点、动作模态、既有控制去重、Package114/116隔离、claims_complete=false及无跨包污染。 | `runs/execution/phase5-package115-contraception-method-authority-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
