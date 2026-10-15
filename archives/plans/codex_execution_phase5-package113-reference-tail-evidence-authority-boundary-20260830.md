# Codex Execution Plan: phase5-package113-reference-tail-evidence-authority-boundary-20260830

Objective: 在D001 II期当前不可变131包计划中，完成Package113 body.p1307-p1308参考文献尾部与方案正文权威边界语义闭环；逐项判断DLQI论文题录和药品注册管理办法题录是否形成参与研究前控制，不从题录反向生成DLQI评分算法、阈值、受试者资格或药品注册程序，保持Package112/114及body.p1309空白边界，产出最小配置、父级临床清单、确定性回归、独立攻击验收和可恢复记录，不进入临床语义模型发布、受试者、OCR、Patient Profile、浏览器或视觉阶段。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | worker_01：只读核对冻结计划Package113身份、body.p1307-p1308两项拥有来源原文、38项只读语境及Package112/114边界；逐项判断参考文献题录与方案正文控制的权威层级。 | `runs/execution/phase5-package113-reference-tail-evidence-authority-boundary-20260830/worker_01.md` |
| `worker_02` | worker_02：在父级补齐Source of Truth与授权路径后，于Package113授权路径内创建最小配置、父级临床清单和专项回归，运行模型外dry-run；不得从DLQI或药品注册管理办法题录自由生成受试者阈值、评分算法、执行程序或监管流程。 | `runs/execution/phase5-package113-reference-tail-evidence-authority-boundary-20260830/worker_02.md` |
| `worker_03` | worker_03：只读独立攻击Package113方案，重点查题录候选化、DLQI算法或切点臆造、药品注册办法程序化、相邻Package112/114吸收、body.p1309空白泄漏、context升格及冻结身份漂移。 | `runs/execution/phase5-package113-reference-tail-evidence-authority-boundary-20260830/worker_03.md` |
| `worker_04` | worker_04：待父级复核后只读验收实际工件；复跑专项、相邻包和共享语义回归及dry-run，核对所有权、38项语境隔离、Package112/114不吸收、两项题录不反向生成控制、每项处置有原文依据、claims_complete=false及无跨包污染。 | `runs/execution/phase5-package113-reference-tail-evidence-authority-boundary-20260830/worker_04.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Execution Order And Boundaries

1. `worker_01` and `worker_03` independently inspect the frozen source and boundaries read-only.
2. `worker_02` may create only the four Package113 paths authorized in the execution context and run the focused model-free checks.
3. Codex reviews the actual artifacts against both read-only reports and the frozen source.
4. `worker_04` runs only after those artifacts exist, remains read-only, and performs independent focused, adjacent-package and shared regression acceptance.

The parent decision baseline is: both owned rows are bibliographic citations and use the existing `non_enrollment_execution` disposition; neither creates a subject-level candidate. This remains subject to source-by-source verification. Do not add a new domain enum, absorb `body.p1306`, `body.p1309` or `body.p1310+`, or infer DLQI scoring/thresholds or drug-registration procedures from citation titles.

## Codex Acceptance

ACCEPT。Codex已核对冻结原文、Package113工件、四路执行报告和确定性回归。两项题录均保持
`non_enrollment_execution`，不反向生成DLQI评分/阈值、受试者资格或药品注册程序。真实DLQI执行内容
仍由Package74/125/128的方案正文与附录来源持有；Package112、Package114及无主p1309均未吸入。
Package113专项29项、Package103-113组合回归279项、slice59n共享回归39项均通过；`claims_complete=false`，
未调用临床语义模型、未发布，未进入受试者、OCR、Patient Profile、浏览器或视觉阶段。
