# 2026-09-22 本轮审阅证据

## 已执行
- git worktree list、git status --short：目标树HEAD e7f34d0508c05481164cf13569f66ddf64e2e74f，开始clean；主checkout d53caa5f，不混用。
- gh api repos/smkzw/enrollment-review-app/branches/codex%2Fphase5-clinical-facts-profile：同HEAD；open pull requests查询返回空。本轮无PR创建、提交或推送。
- 专家ZIP列表17文件；解包后SHA256SUMS中的16条全部相符，原包保留。未执行其probe脚本。
- app/scripts Python AST盘点：592文件、211151行、无SyntaxError；一个invalid escape SyntaxWarning。静态语法通过不证明业务正确。
- app/frontend/src目录盘点817文件；对4caf392c..HEAD的app/frontend/scripts/tests差异统计494文件、49747 insertions、2086 deletions。仅盘点，不称逐行全部审阅。
- frontend `npm run build`，exit=1，实际installed TypeScript 7.0.2：
  - labels.ts:142 TS2353 pending_control_applicability不在ExpectationStatus。
  - mappers.ts:164 TS7053 GapType control_applicability_pending不在GapCountsWire。
  - EligibilityWorkbenchPage.test.tsx:3 TS6133 cleanup未用。
  - 同test:250 TS2339 parentElement调用对象类型错误。
  - 同test:267 TS2322 actionOwner可undefined不匹配View。
  - EligibilityWorkbenchPage.tsx:365 TS6133 severityOf未用。
- 一次pytest（06给完整命令）：14 failed、20 passed、2 xfailed，10.86秒，exit=1。大部分投影失败到assessment.py:277“审核节点或资料要求的到期节点不完整”；语义绑定一项期望source_conflict实得observation_selection_unverified。两xfail本来标记类别别名缺资格。尚未判定所有失败为产品或fixture，W1集中分类。

## 不计作已执行
没有新方案/病例运行、没有全库pytest、没有Ego截图、美学验收、DB迁移或正式签发。用户追加要求后执行11次最小端点诊断，6次缺会话头失败，隔离兼容组4成功/1上游失败，详见10及两份原始回执；不是临床验收。143事实/69未决/20成功页来自前任交接，不是本轮重验。
全库语法盘点和相关测试不能证明全部源码正确。本轮Review对核心功能链做深入核对，长尾模块在W6/W7集中验收中补齐。

## 独立审阅
批准C03 packet enrollment-0922-plan-review实际执行完成，runner exit=0，ok=true，1 round，无fallback。回执effective_agent=grok、provider=grok-build、model=grok-4.7、effort=high；session=9f4f7581-49cc-4a26-99ce-d20411734897。预检返回已鉴权模型目录含请求模型。模型身份以runner/服务声明为限，不称独立验证了供应商权重。
报告：runs/conference/enrollment-0922-plan-review/evidence_single_object.md；结构回执：logs/conference/enrollment-0922-plan-review/evidence_single_object_stdout.txt，output_sha256=97d40893f73e6c5cc7c0fa248afeefa15a4f644a4138ada657bd9f81223bde4a。
评审只读source/文档，没有重跑本轮tests或病例，没有产品写入。它审阅的是整合前计划，认为需收敛三个技术选择再交接；以下由所有者复核裁决并已写入最终包，不冒称修改后再次独立通过：

| 审阅意见 | 所有者裁决 |
|---|---|
| 资格只调用_select_with_ordering，不新造选择器 | 采纳复用、拒绝仅一个helper足够：401行起工厂还有语义命题/频次/复查/书面来源。W1明确从既有完整组装最小提取，共享原实现，授权另层 |
| 有policy仍可能single同值多条误用 | 成立，补Q1同值多观察反例；不声称有policy就安全 |
| 活接口并列controls | 采纳并复用history显示结构；拒绝“零控制+零官方可成功”，总要求为零只能是未就绪/错误 |
| 守望退役，不修补 | 采纳，W0禁止执行旧脚本，复用持久Job |
| self_consistent不作已核；避免第二观察库 | 采纳；更进一步，is_verified布尔本身也必须核实际产物引用 |
| 否定摘要按scope和事实/期望头失效 | 源码有据，W5补具体消费点，不造新失效引擎 |
| 发布错误print/traceback删除 | 非核心交付，不扩大到日志清理专项；相邻发布改动如涉及该分支，保留既有结构化错误与排查证据，不盲目删所有诊断 |
| Q1阻止一切模型调用 | 正式病例/发布遵循Q1；用户追加无病例、无数据写入的最小连通诊断是明确例外，不阻塞其余离线开发 |

专家包和会商意见均非新权限；原始审阅报告保持不变。最终临床和产品验收仍在Q3，未发生。

## 交接文件核查
- task.json与7条implement/check上下文JSONL均可解析，所指文件存在。
- history/20260922-pre-review六份旧任务文件逐字节匹配本轮HEAD，不是仅保留节选。
- delivery目录Markdown显式本地链接无失效；独立审阅输出hash与runner回执一致。
- 本轮新增交付/历史文件扫描无当前.env凭据值匹配；未将.env、病例或数据库纳入资料包。
- git diff --check通过；app/frontend/scripts/tests无本轮已跟踪源码差异。仅规划/指向/证据变更及隔离诊断脚本。
- 产品问题仍待fork实施，未提交/推送、未创建fork，运行时Goal仍paused。当前文档整合完成，不等于工程目标完成。
