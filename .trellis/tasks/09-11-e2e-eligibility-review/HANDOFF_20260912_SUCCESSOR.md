# 入排审核系统 Phase 5 → 下一棒 Agent 完整交接文档

写于 2026-09-12 凌晨。接收方：接手继续构建的下一个 Agent。目标：读完本文即可掌握全局、无缝继续。

---

## 0. 30 秒摘要

单机 Mac 入排审核工作台（AI 辅助，医学监查员使用）。Phase 5（临床事实链 + 入排判定 + 判断检索）工程链路已全线打通并经过独立会商审阅；本会话最后阶段发现并修复了一个**贯穿性根因缺陷**（fact_type 词汇表断链——确定性条款判定从未在真实数据上工作过），修复后真实数据上首次产出确定性判定。当前 HEAD=`45cc774`，工作区干净，全部提交在分支 `codex/phase5-clinical-facts-profile`。`claims_complete=false`，有三件待办在用户侧裁决后继续（详见 §5）。

---

## 1. 来龙去脉（任务规划全景）

### 1.1 项目背景与角色

- **用户**：资深临床试验医学监查员，原生中文，视觉敏感，不熟悉计算机/AI。所有面向用户的文字必须中文原生（不是翻译腔），不得出现工程术语、英文枚举、内部 ID。
- **产品**：本地单机、双击即用的入排审核工作台。AI 领导但**不代替医生做最终入排决定**；系统输出是工作底稿。
- **权威设计文档**：`docs/REARCHITECTURE_FINAL_DESIGN_20260812.md`（用户三轮确认后的最终设计）。关键承诺：
  - L21：**「形成从最早可证明事件到当前审核节点的入排 Patient Profile」**（患者旅程）；
  - L40/441-443：增量上传去重合并；全量上传新快照；增量展示"重复/已合并/新增/受影响规则"；
  - L188：后台保存**全量事实**，首屏只突出入排相关/异常/临界/风险；
  - 医学红线：**无判断≠阴性；未核实≠缺失**；确定性条款代码判定、专业判断条款不猜；来源可回溯；后期资料不改写早期结论。

### 1.2 Phase 5 的任务与完成态

Phase 5 = 临床事实链（上传→OCR→事实归一化→发布）→ 入排判定（规则解构→期望投影→求值）→ 判断检索（书面判断候选双模型检索）。截至交接：

| 模块 | 状态 | 关键证据 |
|---|---|---|
| 事实链 | ✅ | 601 事实/46 事件/22 暴露（QC 核实），定位覆盖 100% |
| 判断检索 | ✅ | runtime06b/c：24 页 48 读步全带回执；7 要求中 6 条有候选、1 条诚实歧义 |
| 入排判定 | ✅（修复后） | 词汇表桥接（34d4f43）后真实数据首次产出确定性判定 |
| 界面验收 | ✅ | 三档视口截图 7 张归档 + 第三方测试 |
| 测试 | ✅ | 后端 4352 通过；前端 564 通过 |

### 1.3 本会话（09-11 → 09-12）的工作时间线

按提交顺序（`git log --oneline` 可查）：
1. `24a8c77` 组链头：冲突组链等早期修复
2. `eaa428d` **P0 修复**：判断检索执行器完成协议签名（3 参）——runtime06 首次真实跑失败（0 回执）的根因
3. `09bfe2b` UI 三修复：档案页延迟、链路漂移、判断卡中文原生
4. `3df9b09` 上下文文档
5. `e72bce6` 独立会商 4 项 findings 闭环 + 三档截图归档（eaa428d 的回归守卫测试含反例验证）
6. `f466bc2` 收口建议报告 v1
7. `15db86a` 深夜暂停记录（第 19 页 429 发现）
8. `406ae9d` 暂停记录 v2（WIP stash）
9. `c061aa6` **429 限流等待修复**：两读器 12×60s 有界等待 + 3 测试
10. `07d9ed3` **系统性发现落盘**：fact_type 词汇表断链
11. `34d4f43` **C 方案桥接**：谓词/事实词汇表打通 + 终局判定 reason 一致性修复
12. `f7a54e5` 收口建议 §五 更新
13. `15a3637` task notes
14. `45cc774` 第三方测试修复：理由通顺句 + 候选点击未关联页提示

---

## 2. 已实现 vs 未实现（深度分析）

### 2.1 已实现（有直接当前证据）

- **判断检索全链**：正式入口→持久作业→双读（GLM-5.3-flash + Gemini 3.7 flash）→摘要→界面卡片。48/48 读步带回执。6/7 要求 candidates_present。
- **词汇表桥接（34d4f43，本会话最重要产出）**：`EvaluationContext.predicate_fact_type_aliases`（谓词键→允许事实类型集合），投影层从组件 evidence_requirements 的 fact_type 生成映射。真实库效果：筛选「55PJ+26 未到期、零确定性」→「21PJ+14 未触发+2 满足+26 未到期+18 冲突」；基线「81 全 PJ」→「54PJ+18 未触发+9 冲突」。决策-文案矛盾 0。
- **429 有界等待**：c061aa6。GLM 限流不再被 2 次硬重试耗尽。
- **31001 原件 QC**（`QC_31001_20260911.md`）：22 条用药暴露完整；「0 暴露」= runtime05 run 级口径（partial run 收尾重建档案时以 run_id 过滤，坍缩见 §2.2-G1）；判断检索 7 要求 ↔ PJ 期望 7:7 闭环。
- **测试基线**：后端 4352/0 失败；前端 564/564。聚焦回归（投影 12/12、API 3/3、429 3/3、前端 14/14）。

### 2.2 未实现/已知问题（按严重度）

**G1【高危·数据正确性】partial run 档案坍缩**
- 机制：`fact_normalization_executor.py:1299-1304` run 收尾 `generate(run_id=publication.run_id)` → `patient_profile_service.py:342/356/370/390` 四处按 run_id 过滤 → **上一 run 的发布实体从档案消失**（QC_31001 实证：medication 泳道 33→2 条）。对照：`fact_correction_service.py:1163-1172` 修正路径**不传 run_id**（全权威口径）——同一服务两种口径。
- 为何平时无症状：正常 run 强制全页覆盖（planning 层 validate_full_page_closure），run_id 过滤后仍是全量链头；只有 **partial run**（如 runtime05 的 37/601）才坍缩。
- **用户裁决已给出方向**（交接前最后指令）：「第一次上传全量展示，之后全量+增量；区分筛选期/基线期；显示患者旅程」。完整差距清单见 `agent://JourneyAudit`（7 项差距，含 UI 概念：节点切换+旅程泳道+增量标记）。

**G2【高危·判定语义】桥接后判定质量复核未完成**
- ClinicalReview（`agent://ClinicalReview`，transcript: history://ClinicalReview）跑完 45 分钟但最终结构化输出因 GLM 429（5 小时限额）失败，其过程记录揭示两个**真问题**：
  1. **EX-07e 例外接管缺陷**：trigger=TRUE + exception=TRUE → 判「未触发排除标准」——trigger 与 exception 两个语义相反谓词命中同一条 allergy_history 事实，终局判定依据矛盾。唯一走例外接管路径的条款，但医学上不可接受。
  2. **IN-03「症状控制不佳」investigator_judgment 条款被判 inclusion_met**：声明需研究者判断的条款被代码下了终局结论——触碰「专业判断条款不猜」红线。桥接把"任意 affirmed 记录存在"当"满足"。
- **这两个必须修**：修法方向——determination_mode=investigator_judgment 的条款永远不产出终局判定（保持 PJ+检索候选）；exception 谓词与 trigger 谓词命中同一事实时降级 conflict。

**G3【中·判定可信度】18 条筛选 conflict 是"同页多事实"误触发**
- EX-07 疱疹/鼻窦炎/结核等 5 条共享同一组病史"否认…"事实，界面只说"存在冲突"不说冲突内容。第三方测试 P1-2。修法：conflict 卡片并列展示冲突事实原文+页码（候选 API 已有 excerpt 能力）；ClinicalReview 建议复核 conflict 判定树。

**G4【中·旅程】Patient Journey 视图缺失**
- SubjectsPage 每节点独立档案、无跨节点旅程聚合；档案历史端点已实现（`app/api/v2/patient_profiles.py:111-133`）但前端未消费。见 `agent://JourneyAudit` §UI 概念。

**G5【中·链路】用药史观察压制的真正根因=字段粒度对齐**
- 病历 p5 两主读字段粒度完全不同（main-A 按药名 23 字段 vs main-B 按大项 11 字段，交集仅 8 个体征项）→ explicit_conflict_fields 无同 key 可比 → 40 条观察全部 page_observation_unverified 压制。targeted 通道正确拒绝（该页无数值/日期/标记分歧）。这是 09-08 已记录的"受限语义对应隔离"试验范围，**未获用户扩测授权前不要动提示词**。

**G6【低】零散**：run.sh 启动的是 legacy v1 非 V2（P2 文档）；EX-06 子条款 determination_mode 不一致；not_due 带 fact_refs 口径；候选与档案 locator 的 page/source 口径根治（当前已有降级提示，45cc774）。

---

## 3. 当前节点分析

### 3.1 处在什么节点

Phase 5 工程建设**实质完成**（含一个贯穿性根因修复），卡在「判定语义可信度」的最后关卡：G2 两个真问题不修，桥接产出的终局判定不能交给医生看。用户已明确"整个工程构建期间不需要我逐项核对"——构建/测试自主推进，医学结论类决策仍需用户确认。

### 3.2 goal 原文（必须完整保留，不得缩小范围）

> 继续实施构建。注意充分利用orchestra+多sk role模型机制。注意读取最新全局AGENTS.md，遵循方法学、多sk roles model执行/会商机制及模型、Token节省机制。按照Trellis方式进行项目文件管理。定期进行阶段性清理，将不再使用的、旧版的过程文件、缓存文件、测试记录等等进行清理。
> 务必要从用户（懒惰、视觉敏感、不熟悉计算机知识和AI使用的原生中文背景资深临床试验医学监查人员）视角去看问题、查问题、想如何构建、计划哪些细节功能、用怎样的框架逻辑去引导Agent解构预筛/筛选期/基线期的规则、设计怎样的细节交互、使用怎样的视觉设计等等等等的内容。
> 测试者工作期间、执行/会商期间，请保持超长轮询。测试者、执行/会商首次启用要先进行连通性测试，不同harness调用方式存在差别，不要随意fallback。
> 每一步出现预期之外的结果（比如独立Agent没获取到任何方案入排标准、解析后的入排标准条目与研究方案不匹配、没获取到任何受试者病史背景信息等等），构建者、测试者都要去深挖背后的原因，不是说能跑通、html报告能看、流程能通就完了，是要模拟真实的人去真实构建、真实使用这个系统，真实的人遇到预期之外的反馈第一时间是去深挖为何出现这种情况，而不是无脑采信这个雏形系统！始终以第一性原理做构建和测试，始终以批判视角做构建和测试！每轮测试后的旧版文件、缓存、测试文件等等要定期清理。
> 所有的文字、标签等等，都需要中文原生（而不是翻译），且必须把程序员用语、后端标签、log类标签清空，如"xx门"、"xx信号"、纯英文标记等等，针对用户的中文语言要进行原生中文临床试验环境的针对性会商。
> 不需要针对系统做任何安全性的测试、担心，聚焦于面向用户的系统功能构建、测试即可。

### 3.3 goal 实施阶段分析

- **已完成阶段**：Phase 5 全链工程（事实/判定/检索/界面）+ 本会话三连修（429/桥接/UX）+ 独立会商闭环 + 第三方测试。
- **进行中**：多模型复盘三 agent——JourneyAudit ✅（agent://JourneyAudit）、ThirdPartyTest ✅（agent://ThirdPartyTest）、ClinicalReview/CodeReview 过程完成但结构化输出被 GLM 5 小时限额打断（**16:04:59 重置**；transcript 在 history://ClinicalReview、history://CodeReview，过程发现已提炼进本文 §2.2-G2/G3）。
- **下一阶段（按优先级）**：
  1. **修 G2 两判定语义缺陷**（investigator_judgment 不给终局；例外接管矛盾降级 conflict）→ 重跑真实库验证分布 → 前端回归；
  2. **修 G1 档案口径**（run 收尾 generate 去掉 run_id 过滤=全权威口径，与修正路径一致；JourneyAudit 有完整论证）；
  3. **患者旅程视图**（G4，UI 概念见 JourneyAudit）；
  4. **conflict 卡片并列冲突事实**（G3）；
  5. 全部完成后回写 Phase 5 PRD/claims_complete（需用户确认），Phase 5.5 含 A 方案词汇表深度对齐评估。

### 3.4 关键操作知识（避免踩坑）

- **环境**：worktree 路径 `/Users/smkzw/Documents/康哲项目资料/AI/入排/enrollment-review-app/.worktrees/phase5-clinical-facts-profile`。Python 用 `.venv/bin/python`（homebrew python3 缺依赖）。前端 `cd frontend && npx vitest run`。
- **启动 V2 后端**（供浏览器测试）：`ENROLLMENT_ENV_FILE=$W/.env ENROLLMENT_V2_DATA_DIR=$W/artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry .venv/bin/python -m uvicorn app.api.v2.app:create_app --factory --port 8907`。**run.sh 是 legacy v1，不要用**。
- **测试数据根**：06c = 最新（含桥接后判定 + 48/48 检索回执）；06b = 429 前成功证据；e2e-runtime06 = P0 失败现场。**全部保留不删**。
- **模型调用**：GLM 5.3 flash 有 5 小时限额（重置 09-12 16:04）；429 等待已内置读器。连真实模型前先 1 次极小直连探测。
- **Trellis 任务目录**：`.trellis/tasks/09-11-e2e-eligibility-review/`——所有权威文档都在这（见 §4）。
- **承诺边界**：不动 06b/06c 原库做手工 SQL（重置只能做副本）；不擅自改提示词扩测语义对应；中文原生边界；无安全性测试。
- **sub-agent 纪律**：GLM 限额被打断的 agent，过程结论可从 transcript 提炼（history://<id>），勿盲目重跑 45 分钟长任务；先查限额重置时间。

---

## 4. 权威文档索引（全部相对 worktree 根）

| 文档 | 内容 |
|---|---|
| `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` | **最高权威**：最终设计（L21 旅程/L40 上传/L441 增量展示/L188 全量事实） |
| `docs/PROJECT_CONTEXT.md` | 项目状态摘要（顶部 09-11 条目） |
| `.trellis/tasks/09-11-e2e-eligibility-review/PHASE5_CLOSEOUT_RECOMMENDATION_20260911.md` | 收口建议（§五=最新状态） |
| `.trellis/tasks/09-11-e2e-eligibility-review/QC_31001_20260911.md` | 31001 原件 QC（22 暴露/run 口径/人工清单 5 项） |
| `.trellis/tasks/09-11-e2e-eligibility-review/FINDING_20260911_FACT_TYPE_DISCONNECT.md` | 词汇表断链发现（含 A/B/C 方案） |
| `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260911_OMP_PAUSE.md` | 会话总入口（第一份暂停记录） |
| `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260911_LATE_PAUSE.md` | 429 发现与 SQL 重置步骤 |
| `.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260911_FINAL_PAUSE.md` | WIP stash 记录 |
| `agent://JourneyAudit` | Patient Journey 设计符合性审阅（7 差距+UI 概念） |
| `agent://ThirdPartyTest` | 第三方测试报告（14 发现，P1-1 已修） |
| `agent://ClinicalReview` / `history://ClinicalReview` | 医学审阅过程（EX-07e/IN-03 两缺陷证据链） |
| `history://CodeReview` | 代码审阅过程（桥接实现细节疑点） |
| `artifacts/phase55-takeover/20260911/glm-gemini-runtime-06c-page19-retry/` | 最新测试数据根（06c） |

---

## 5. 立即可执行的下一步（建议顺序）

1. **修 G2-1**：`app/domain/gates/assessment.py` 的 `derive_component_decision`——`determination_mode=investigator_judgment` 的组件永远返回 PJ（不产出终局）。数据源：clause.determination_mode 已在投影层。
2. **修 G2-2**：`_evaluate_logical` 例外接管——trigger 与 exception 命中同一事实（fact_id 交集非空）时整体降级 UNKNOWN+conflict，而非 exception=TRUE→未触发。
3. 重跑真实库（§3.4 启动方式）验证分布变化 + 前端 `npx vitest run` + 后端聚焦回归。
4. **修 G1**：`fact_normalization_executor.py:1299` 去掉 `run_id=publication.run_id`（与修正路径口径统一）。加测试：partial run 后档案仍含上一 run 实体（现行为 33→2 坍缩，修后应保持 33）。
5. 提交后更新 `PHASE5_CLOSEOUT` §五，向用户汇报判定分布的新变化。
6. 之后：患者旅程视图（G4）→ conflict 卡片（G3）→ claims_complete 用户确认。

**一句话心态**：用户是医生不是工程师——界面每个字都要让医生一眼看懂；系统每个"无法判定"都要说清差什么；永不把"没找到记录"说成"没有病"。
