# HANDOFF｜1006V1｜资料恢复与UI更正成立，完整工作稿未达

记录日期2026-10-06（Europe/Rome）。现场Goal已查active，任务in_progress，用户暂停已解除；不是新增暂停点。窗口尚未达，claims_complete=false。用户明确测试调用次数不设硬上限，要求尽快完成、不钻牛角尖；旧12次保持历史，新v2已终态失败，6新调用、总18，不把停止同失败分支说成暂停所有工作。普通工程提交不等于规则激活、事实自动采用或临床签发。

当前增量：前端0e9b9bb99643ad074b2033d408ed8b7fc3dd1936消除原件展开后的短列表空白列，节点栏收拢受试者选择；相连27项与构建通过，Ego1080P/2K/4K实际截图均无横溢出，关闭恢复列表。0c6f40291e95eae6fce17467d02f75b4d14890ca进一步收拢正文：普通报告医师/申请医生/打印/页码省略，临床记录、研究者书面判断及关联/待核保留，原始索引不删。4相连模块33passed/3.36s，正式构建exit0；Ego实际Profile4原198项/展示190项，未打开原件时列表sticky仍可见，top68避开52顶栏。截图仅本机受控，非完整Q3；旧调用账本及身份保护不变。

## 1. 一句话回答用户

档案精简最终源09e00e63f528fe1db6cd8139f0c716c82c9926ad追加“行政字段带临床批注仍保留”，覆盖CS/NCS与临床意义判断。四相连模块最终34passed/3.41s，正式build exit0；与前33项重叠，不能累计成67。原始记录、定位、采用状态和历史均不变。

已读完本次5份24页资料并保存可进入档案的内容，医学经理已能从实际界面查看原件、修订一条描述并回看新旧档案；**尚未在完整官方＋跨章要求下生成本例工作稿，更没有更正后的新审核报告**。

| 身份 | 实际值 |
|---|---|
| 唯一工作树/分支 | /Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile；codex/phase5-clinical-facts-profile |
| 开始基线 | 7b3ed4f9251323b3194371764f2bcd17ad94559e；此前产品源码8b5b4c4f75f85110dfc81ce080755b1c8457144f |
| 本轮产品代码 | 后端cc4048348f12afde4d3221415e884c7966e5bf4c；布局0e9b9bb99643ad074b2033d408ed8b7fc3dd1936；临床展示0c6f40291e95eae6fce17467d02f75b4d14890ca。精确hash见SOURCE_SNAPSHOT_20261006_1006V1.json，历史快照字段不被新文件覆盖 |
| 实际测试/真实运行的代码 | 后端643与cc404834一致，v2真实请求冻结0e9b9bb9且app源码仍同cc；未到目标核对，不能宣称v7临床效果。前端31/27/33及各Ego分别绑定对应源码。P2恢复/更正用基线后端 |
| 外部可复核 | Git源码、合成正反例、当前review_index、净化事实/调用汇总、两次工程顾问报告 |
| 仅本机可读 | 以下tmp目录的原件/数据库/原答/截图/私有驱动。未提供外部审阅；hash只证明身份，不证明临床含义 |

五分钟入口：本HANDOFF → implement文头D0–D5 → delivery_1006V1/03_ACCEPTANCE.md → review_index_20261006_1006V1.json → SOURCE_SNAPSHOT_20261006_1006V1.json。再按具体首错读函数，不读全部历史。旧暂停和历轮交接保留为历史证据。

## 2. 同一用户流程的结果

| 节点 | 已证 | 仍未证/不能拼接 |
|---|---|---|
| 完整要求快照 | 内置DOCX官方草稿rev2，23条82组件，带前版/diff门禁publishable=true；跨章发现/闭包可保存 | 尚未共同采用；跨章60深审批首批失败、59未读。25项23预览和局部26陈述不能代完整范围；旧P2库81组件0controls不能拼成新要求包 |
| 资料处置与资格/Profile | 14组/5文件24页均有处置；第7组恢复首次保存回答，前6成功检查点不变，余7实际读取；458候选、32可事务候选合并为30事实，Profile第3版 | run仍partial；426阻断、584未决、5冲突组、55档案待核；0事件/0暴露/0规则关联。未定位数值/日期不可借文字正确自动采用，也不证明其余候选临床错误 |
| 当前节点工作稿与原件 | Ego空间114/p1真实进入正式个例/筛选/资料/档案及历史，原图第8页自动定位可核 | eligibility-review API真实not_started；无完整同源工作稿/报告，C1/C4未达。不造红框，没有像素证明只定位页面 |
| 更正与历史 | 实际UI预览→确认→提交一条有原文依据的对象描述修订，合法新Job37.1176s/0模型调用；新事实和Profile第4版，旧payload hash不变 | 未修改临床值；此为档案描述更正，不宣称旧入排判决错误。0规则关联，未发生新审核报告重算，C8未达 |

P2私有根：/Users/smkzw/tmp/enrollment-rv1001-case-source-consumer-20261006-v2；数据副本rv1006-saved-response-current-node-20261006-v1/data。项目draft-project-09b593a721e7，方案draft-version-09b593a721e7，个例rv29-preparation-20261001，节点e8615813d75b452489579ff9606781b4/rev3，快照64f85a6d0e844c45a39ca6d05a104c06，准备complete-46de236068d84b299ff41e35215d5fc5。此处保留身份供本机恢复，外部无临床内容可读。

## 3. 本轮处理的实际阻断

| ID | 第一因果问题 | 处置/消费者/反例 |
|---|---|---|
| F1 保存初答恢复未实跑 | 前轮仅预检，第7组重读又产生来源别名错误 | 保护库SQLite一致备份＋APFS clone，沿原Job合法retry、显式opt-in已保存首次完整回答。真实保存/汇总/Profile/读回成立；原失败、原件、前6检查点及其他旧Job不变。不改变来源/位置/数值资格 |
| F2 界面原样显示true/false | 中文档案记录结果显示工程布尔字样 | ProfileItemCard仅布尔值显示是/否；0和文字串false不转换。4前端模块、正式构建及实际页面核对；不改极性/断言含义 |
| F3 跨章核对混用编号 | 初始目标核对10项使用原文位置source_ref而非structure_unit_id，首错落在陈述7；局部纠正正确返回canonical ID，下一兄弟陈述8仍用初始错编号 | 未自动替换答案。只读两项替换试验各过原关系检查，但不保存/采用/推断整批；C03挑战后主提示v7明确字段，CONTEXT_TARGET_ID_INVALID类型化拒绝。合法canonical、重复source_ref、namespace碰撞、未知ID及语义变化反例保持；消费者不放宽，新提示未实跑 |
| F4 旧读取复用身份失效 | 原/当前来源分包hash相同，首个来源读取实际消息相同，但prompt材料/整套wire Schema及response_format路线身份变化 | 只读当前预检60批refresh_required；原首批partial_wire为空，非损坏wire。未扩建跨版本恢复/未改旧hash/未靠提示版本白名单复用。用原剩余额度一次现行第一组尝试，未读其余59组 |
| F5 当前第一组流程关联错误 | 新v2来源阶段遗漏局部修复后，候选将不同执行节点的流程项关联到不匹配的决定节点；两次完整候选生成仍不一致 | failed_final/DEEP_OUTPUT_INVALID，不能因无硬次数上限反复生成整包。首错层是解释/候选关系装配，非端点故障/额度不足。先冻结出错关系与原流程目标核是否真实补充或独立义务，再经已有局部修订/完整校验；不得删真实要求、改时点凑目标或放松阶段资格 |
| F6 档案噪声 | OCR行政字段与临床记录等权铺开；无原件长页列表随滚动离开留下空列 | 仅前端展示投影，不删事实或历史；实际原198/展示190，临床检查仍可回源，列表保持可见。不新增临床类型猜测或模型请求 |

主动延后：跨版本来源/部分wire复用扩展、自动source_ref规范化、模型榜单、bundle性能优化、通用恢复UI。它们未被用作通行证。主工作台适配只完成所有者亲自评估：既有App统一新建项目已消费handoff，宜用Option A；本子系统V2与共享/api/projects身份桥接未证。不重复消费sessionStorage、不修改首屏、不把“未改”说成集成通过。

## 4. 验证与调用

| ID | 实际命令/入口 | 终态与边界 |
|---|---|---|
| T1 | .venv/bin/python -m pytest tests/v2/protocols/test_slice58c_control_deconstructor.py tests/v2/services/test_protocol_control_execution.py -q --tb=short --junitxml=/Users/smkzw/tmp/enrollment-rv1001-official-continuation-20261003/rv1006-context-id-connected-v1.xml | 643passed/43.73s/exit0/5SWIG警告；合成原模块和消费边界，不证明临床或新提示真实效果 |
| T2 | frontend内npm test -- src/components/profile/ProfileItemCard.test.tsx src/components/profile/ProfileEvidencePanel.test.tsx src/components/profile/ProfileFactCorrectionDialog.test.tsx src/components/profile/ProfileCorrectionHistory.test.tsx | 4文件31passed/2.13s/exit0；npm run build出口0，既有大bundle警告；旧178后端检查未重跑不相加 |
| T3 | 私有run_saved_response_window_20261006.py，合法同Job受控副本恢复 | Job4b08b1fd8b9c4faabf3a98db5e6ebad6/run708d246c05444fc3990348db1884f9e4，1429.0923s/exit0、completed/运行partial。第7组恢复新增0模型调用，但旧100.281s/20952输入43081输出费用不归零；余7组实际读取，汇总token/费用本轮未完整对账记unknown |
| T4 | 私有audit_rv1006_deep_resume.py，只读原库→审计副本 | 0模型/0Job入队；旧库hash不变，旧first step无租约/failed_final；实际组成差异而非猜缓存损坏 |
| T5 | 显式env＋PYTHONPATH＋私有run_rv1006_current_control_window.py prepare/execute，产品API创建Jobbb3ab7946f3243769bfec34dfa94a0ab | 405.1088s/exit3、failed_final/PROTOCOL_CONTROL_LOGICAL_BUDGET_EXHAUSTED；新7物理调用+旧5=12/12，不因新Job重置。输入113771/输出109901/总223672，输入缓存1728已包含不另加；思考细分/费用null。全部stop，非断流故障；旧库/旧Jobhash不变，9诊断attempt不等于9物理调用 |
| T6 | Ego真实1920×1080/缩放1，正式Profile更正及历史/原图导航 | 修订Job5d4d8c58b5e2400291da0273366ad5ea，37.1176s/exit0，0模型，新Profile profile:2885bd6aa6bcebba4524d1ca5cb32f07/rev4；截图仅受控本机。0关联规则，因此不是报告闭环 |
| T7 | 两次C03独立静态挑战 | CodeBuddy/codebuddy-cli/DeepSeek-v4.1-flash/max，200.079s和239.98s，均exit0/no fallback；120min完成等待主线程静默。顾问未读病例/DB、未测、不是独立模型金标或医学批准 |
| T8 | 1006V1 MANIFEST七文件hash/字节、git diff --check | 出口0；PACKAGE_CHECKS是包作者报告，本轮另核实际hash。全库/留出/启动恢复/完整Q3未运行，2K/4K仅布局已核 |
| T9 | 私有run_rv1006_authorized_control_window.py，新API Job09e55762a458420ca72dcea22bdd25ce | 326.497161625s/exit3/6新物理调用，failed_final/PROTOCOL_CONTROL_DEEP_OUTPUT_INVALID；旧12不变，总18。来源局部修复后两次PROCEDURE_AFFECTED_STAGE_MISMATCH，未到目标ID核对。原库与旧作业保护true；请求/原答本机受控 |
| T10 | npm test -- src/components/profile/ProfileLaneList.test.tsx src/features/patient-profile/model/patientProfileModel.test.ts src/components/profile/ProfileHighlights.test.tsx src/pages/SubjectsPage.test.tsx；npm run build；Ego114/只读52507 | 4模块33passed/3.36s/exit0、TS/Vite exit0；后续CSS避开顶栏经最终正式构建与Ego核，原198/展示190、行政标题0、无溢出，列表top68。PID12658/session77157退出130，无模型/临床写入 |

T5首错顺序：STUDY_PHASE_NOT_VISIT_STAGE → 局部纠正 → FUTURE_PROHIBITION_DECIDED_EARLY/TREATMENT_DURATION_USED_AS_EVENT_WINDOW → 局部修订后wire解析成立 → 主目标核对CONTEXT_RELATION_UNGROUNDED → 首项编号更正成立 → 下一项同初始错编号 → 累计预算拒绝。不是所有时间都耗在一个慢模型上，也不是端点不可用。

当前批准产品角色：官方cms-router/GLM-5.3-flash/high经OmniRouter（本轮未新调）；跨章及规范化ollama-cloud/DeepSeek-v4.1-flash/high，试跑输出上限65536。工程C03个人CLI只作代码顾问，不替产品读病例。当前没有启动本地MTPLX或另一模型，未配置新供应商/下载。

## 5. 复盘：事实与建议分开

支持“恢复成本及合同表达也是主要耗时源”的证据：原初答恢复让余7组走完；同一错误编号在初答多项重复出现，逐项反馈消耗剩余次数；新旧格式绑定影响可复用范围。支持“只加提示不能保证临床完整”的证据：本轮正常stop后仍有期别、未来义务、持续期/事件窗与目标对应错。反证/未知：本轮没有同终点BASELINE/FLOW对照、独立留出或完整病历QC，不能宣称新机制胜出、模型上限或已无过拟合。合理替代解释：来源上下文本身复杂、模型归纳错误及既有消费者未资格化共同导致，不应全归因某一模型或全部取消门禁。

本轮经验：先按一次用户动作判断收益。资料/档案修订确有进展；更正存库不是审核报告重算。预检的真相来自实际消息/Schema，不来自文件名。类型化反馈应准确区分编号错误与临床关系不足；不以词表、自动猜别名或背景重分类“消灭”失败。先冻结、功能包集中回归，再判断是否值得付真实读取成本，不继续逐错误新建整方案长作业。

执行自身问题亦保留：若干只读命令最初猜了不存在文件路径/字段；审计第一次错误遍历None partial_wire，已修审计不归产品故障；一次收据摘要glob过宽误读取request/response大对象，后限定receipt-*.json及白名单字段，未提交原答；原件截图缩放切换时尚在滚动中，复开/回当前页定位成立，未虚报查看器bug。无reset/clean、共享关停或原件改写。

## 6. 当前终点和下一步

窗口未达。首个未达节点是C1完整同源要求仍未核清；C4/C8因此也未完成。后59批未读不能改成忠实医学未决；现有P2旧81组件库不能拿来冒充新包。用户无硬次数上限授权已落实，新v2终态失败，旧Job/终态/账本不改。此次失败不证明v7编号提示无效，因为候选阶段错误发生在更前层。

1. 对v2最后两份候选与冻结流程执行节点作局部只读对照，区分错误附加关系、真实独立要求与合同能力缺口，随后按既有局部修订/完整校验推进；不重复同故障或扩重读整本。模型授权已明确，不再询问额度；旧历史及复用资格继续核，不把技术问题改成研究者判断。
2. 完整要求覆盖/共同采用合法后，将本例资料资格沿现有消费者接入工作稿；原有数值正式采用限制不绕过，必要时用已批准的有源人工核对路径，而非逐字段默认签名。
3. 再从正式UI完成相关审核结果重算/新旧报告；留出、2K/4K及运维/Q3尚待最终集中验收，不因本档案更正宣布完成。

仅本轮自有59128临时UI（PID5156/session89840）已正常shutdown/exit130，Runner原本关闭；其他共享服务不动。临床读取/纠正Runner、两次顾问及测试均已终态，没有本轮后台生成作业仍跑。正式规则激活/自动数字采用/临床签发均未做；旧原件/临床库/失败回执不改。7份继承tracked dirty和其他未跟踪临床/过程材料不stage、不删除。普通工程Git递交与专业验收分开；具体push及远端HEAD由最终回执核实，不能据本交接自称全部工作树已递交。
