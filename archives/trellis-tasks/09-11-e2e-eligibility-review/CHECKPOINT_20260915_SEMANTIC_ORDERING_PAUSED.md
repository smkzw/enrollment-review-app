# 2026-09-15 无损暂停：语义观察顺序

## 权威与状态

用户最新指令：完成手头任务后无损暂停，以非工程语言总结进度、计划位置、下一方向。当前执行已停，不自动恢复。此文优先于PROJECT_CONTEXT下方所有“继续”及旧暂停段。Trellis任务未完成，不归档、不提交，不把暂停标记为目标达成。

唯一工作目录：`/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`。主checkout不写。大量既有未提交文件全部保留；未reset/clean，未改原方案、病例、旧临床库和报告，未清模型缓存。

Goal来源：`/Users/smkzw/.codex/attachments/f3747c04-a1cd-45d0-aeb8-595f3d2530ca/goal-objective.md`。工具读到goal active；现有update_goal只允许complete/blocked，未用其伪造暂停或完成。用户暂停指令与本记录约束执行，不再启动新工作。

最新产品合同：GLM-5.3-Flash high + MTPLX FlashNext OptimizedSpeed xhigh，均完整独立主读；产品自有harness直连、显式env，不调用个人harness。通用来源合同，禁项目/疾病/药名特判。当前用户要求构建完后集中测试，开发只做源码/编译检查；所有新语义采用仍须已有评测与批准。claims_complete=false。

## 本轮实质结果

1. 正式原文命题与跨章控制已经共用原文核实、回执、资格和冻结报告；不把数值/研究者判断/频次改作普通命题以绕过约束。参考前置官方命题review及PROJECT_CONTEXT。
2. 半衰期来源：half_life_evidence保存原文时长、单位、适用对象与来源；倍数和日历天数分离；来源缺失保留疑问。精确时长遮盖防止11天被1天误删。日期无时刻用可能区间，已明确不足的日历要求不会被另一个未知要求掩盖。具体时刻尚未消费；复杂PK语句不自动取值。这不是完整半衰期临床能力验收。
3. 本次已完成的手头增量：语义最近/最早选择。新semantic_observation_selection复用既有日期选择器；全部所供候选内容和日期先核实，再按明确方案window_order选择。失败内容不能被静默丢掉来采用更旧记录；缺日期、同日并列/部分日期无法排序保持未定。双族接线；较早/窗外未选原件与仍未核实原件分开，不混入已用事实。
4. 控制零关系结果改为原文未核实/范围不完整，不再残留“不支持算术”原因；新控制v3所有模式必须显式观察政策或unresolved。官方解构早已要求policy并含latest/earliest，不需另建同功能。
5. 当前版本：DNFv4；control-evaluation/v3；control-wire/v9、prompt/v2.5、publication-gate/v9；qualified-selection/v5、consumer/v14、authorization/v5；proposition/v6、job/v3、consumer/v6；workflow/v5；component-review/v20；frozen-publication/v6。旧版本能读不取得新方法权限。

## 验证与会商边界

- 本次所有者最终9个相关Python文件py_compile通过，git diff --check通过。半衰期前端tsc此前通过；本次排序未改前端。没有新测试文件/阶段测试、模型、应用、数据库、浏览器运行；不是完整产品或临床验收。
- E03 `r05-semantic-ordering-20260915`：pi/cursor/default selector，底层身份未知；session01a0a373-9475-7000-a45e-fca18cbd9152，246.632秒，exit0/no fallback。执行者失败尝试递归worker及额外package import，已明确记录不合边界；其系统Python缺SQLAlchemy不能当作项目.venv缺依赖。产出新helper，所有者另加身份检查并整合。
- C03 `r05-semantic-ordering-review-20260915`：primary grok退出1无session，原因不明，不能说模型不可用。声明fallback pi/cursor/cursor-grok-4.6/high，同session01a0a37a-f598-7000-ac03-07a522b69810，两轮326.093/231.290秒、exit0/empty stderr。源码复审PASS。底层执行模型未知，不能声称完全模型独立。
- 顾问首轮提出日期命题注入、官方审计未发布、需额外v15；所有者找完整input/validator/receipt、publication和本轮版本事实后，顾问撤回。拒绝顾问“删除核对失败内容再选”的建议，因可能掩盖真正最近记录。不要从首轮FAIL摘取已撤回结论。
- 半衰期三轮C03记录见 `reviews/codex_conference_r05-half-life-source-20260915_review.md`；最终组合窗修订为所有者源码核查，不伪称后续独立审阅。
- 所有上述exec已终态；最近execution9349、conference35523、followup19654均exit0；wait cells2355/2367/2372全部完成。无本线程未完成执行/会商或需要继续等待的服务。未终止其他session拥有的进程。

## 整体计划位置

仍在T3，跨章要求与完整档案/复杂观察处理的构建，不是最终验收。原件定位、累计档案、审核准备、正式报告/行动、批量处理等已有源码实现，但当前全链与宽屏效果未统一验证。Phase5/5.5仍未验收，不以历史局部通过作当前完成。

## 下次安全动作（仅收到恢复指令后）

1. 重新读全局AGENTS、此文、PROJECT_CONTEXT文头、R3工程设计及RecoveryPlan、goal来源，核当前源码与并行修改。不要自动恢复任何历史模型任务或数据库作业。
2. T3下一单元：条件复查的通用来源关系。必须明确初查/复查关系、触发、许可、独立时限、结果替代/聚合；日期只算已核实关系，不建立关系，不用次数证明许可。优先复用现有双路作业/回执，不开新框架，不仅加空合同。
3. 事件频次：按已核实临床事件而非事实行计数；摘要频次/逐次发作/发生天数分开，禁止虚构扩展；时间与窗口需要明确边界。来源核实及消费/报告一起实现。
4. 时间精度：为原文时刻提供来源绑定的表示/核实/消费，不能只上传时刻文本就解除半衰期边界疑问；interval_condition的顺序若需支持，应完整扩合同而非当资料窗口。
5. 核R06旧引用/累计原件闭合，T6/T7剩余发布与交付（部分已有实现，先核当前源码再排项）。建设完成后才集中真实双模型/ego桌面1080P、2K、4K/原件QC，不提前宣告claims_complete或启用新方法。

## 定位

- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md`
- `plans/REARCHITECTURE_RECOVERY_IMPLEMENTATION_PLAN_20260905.md`
- `docs/PROJECT_CONTEXT.md`
- `reviews/codex_execution_r05-semantic-ordering-20260915_review.md`
- `reviews/codex_conference_r05-semantic-ordering-review-20260915_review.md`
- 实际报告/原回执在对应runs/execution、runs/conference、logs目录。只读结构化抽取JSON，不打印巨大stdout。

暂停时核心文件SHA256：
```
088751e7d39ac860ff663017c442cf1f1ebfa5e772cea2bd4bdc63ab4d8a775d  app/services/semantic_observation_selection.py
2416a215655c8914f643956a56a92a69a53e20c112e18ab5df6e78dc743fad45  app/services/qualified_binding_selection.py
60ba60f3f4ffd8907bb6a7414d1ddec704615f0319ef4646b2477a4488340dff  app/domain/contracts/control_evaluation_spec.py
94f5d66993ddecb2f9bc55e4bf3a2a02925bf0335c7f289513670bc6c19f0e4f  app/domain/contracts/qualified_binding_selection.py
6989cd44fa14b05b7bc33beae8b933ff4fa75da10ffc645fbadfd90b6dc46125  app/agents/protocol_control_deconstructor.py
22ed6209469efdaec570740af1da9317c88323e55a76317bbc6ba94253ad96ce  app/services/frozen_review_calculation.py
```
