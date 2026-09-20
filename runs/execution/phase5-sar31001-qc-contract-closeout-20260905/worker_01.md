# 执行输出: phase5-sar31001-qc-contract-closeout-20260905 - worker_01

## 边界与上下文检查

- 仅在 runner 绑定的工作区内操作。初始读取 `context/phase5-sar31001-qc-contract-closeout-20260905_execution_context.md` 与 `plans/codex_execution_phase5-sar31001-qc-contract-closeout-20260905.md`，执行 work item 1（只读审计最新 31001 运行包、候选门禁和活动 Profile，对照原始证据形成逐项可验证的临床 QC 清单）。
- 只读纪律：对运行数据库全部查询使用 SQLite `mode=ro` URI + `PRAGMA query_only=ON`；grep/git 仅读；唯一一次测试执行（聚焦 pytest，禁 cache、禁 bytecode 写入）。未修改任何产品源码、数据库、历史证据、`.trellis` 文件；未创建 runner 报告文件（本报告由 runner 持久化）；未启动会商；未读 `.codex/AGENTS.md`/`.hermes/SOUL.md`；未安装任何包。
- 生产路径边界：v12 运行包 manifest 指向的原始 PDF 源目录 `/Users/smkzw/Documents/康哲项目资料/MG-K10/SAR/...` 属生产路径，按硬边界未读取；"原始证据"核对使用工作区内不可变 OCR 层（`ocr_pages.raw_text`，带 raw_text_sha256）。OCR 与纸面原件的字节级一致性属 Codex 验收权，本 worker 未断言。
- 额外读取及理由：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260904_FRESH_RUN_FIX_VERIFIED_QC_GAPS.md` 与 `CHECKPOINT_20260904_PHASE5_HIGH_REASONING_BEFORE_JOB_PAUSED.md`（确定"最新运行"基线与既有 QC 清单）、`runs/execution/phase5-closeout-r3-20260903/worker_01.md`（定位运行包与运行库路径）、`app/domain/gates/fact_candidate_gates.py` 局部（门禁锚点）、`git diff`（只读）。均为完成本项审计所必需。

## 已执行工作

**1. 锁定"最新不可变运行包"三元组（证据链）**

- 最新验证包：`artifacts/phase5-acceptance/20260905/sar-31001-v12-run-packet.json`（generated_at 2026-09-04T22:38:59Z = 09-05 06:38 CST，任务派发前 4 分钟；packet_disposition="verifiable"，blocking_gaps=[]、verification_gaps=[]；包级统计：候选 3567（fact 3067/event 400/exposure 100），门禁结果 14214 accepted / 742 rejected；期望 426）。v11（18:06Z）为其前身。
- 活动权威：patient_profile_revision 指针，快照 `350c8279…`（5 成员文档）、完全处理修订 `complete-5f514e57…`、episode `746385ab…` revision 4、`authority_matches_active_pointers=true`。
- 最新规范化运行：`916bf32f2f0d4ee8b08f187a246cbc9d`（作业 `d513d64e…`，2026-09-04 21:27:01Z 创建，状态 partial = "存在被确定性门禁拒绝的候选"，无页失败），发布 271 事实 / 22 事件 / 8 暴露 / 426 期望 / **Profile 修订 5**（`profile:efa414001f…`，22:36:39Z，payload_sha256 `50d1bae9…`，succeeded）。19 个历史运行 ID 全部登记于 v12 包 run_authority.normalization_runs。

**2. 逐项临床 QC 清单（对照 OCR 原文与全历史修订）**

A. 已恢复/持续通过项（每项均验证到 DB 行 + OCR 原文）：

| # | 项目 | 证据锚点 |
|---|---|---|
| A1 | 心电图 7 参数：HR 85bpm、PR 160ms、QRS 81ms、P 103ms、QT 346ms、QTc 413ms、RV5+SV(L) 1.297mV | `clinical_facts_v2` run 916bf32f 各行；OCR p4 "HR : 85bpm [60～100bmp]"；locator `c786ca3e…` excerpt+sha256+EX-07 requirement 链接完整 |
| A2 | 胆红素三项 30.5/8.7/21.8 μmol/L + 肝功能检验异常汇总（"GGT、TBIL、DBIL、IB超出正常值范围，判定CS肝功能不全"） | facts 总/直/间接胆红素 + 肝功能检验异常 |
| A3 | 肌酐 79 μmol/L、尿素 4.28、白蛋白 49.3、ALP 84、钾/钠/氯/镁/磷 | facts 各行（此前 gap-1 主要损失面） |
| A4 | 家族遗传病病史 negated（obj=遗传病病史 逐字 ✓）+ 家族史(父母) affirmed | facts 两行（此前 gap-2 损失，本运行恢复） |
| A5 | 知情同意书签署 2025-08-08，版本 Master V2.0-site31v01；IN-07 关联 | fact 知情同意书签署 + 事件同日 |
| A6 | 奥马珠单抗 300mg 皮下暴露 + 药物治疗事件 2025-04-05 + 用药史事实 + "治疗效果不佳"（IE 相关既往治疗不佳证据） | exposure 行 + events 药物治疗 + facts；v9 缺口已闭合 |
| A7 | 带状疱疹 2025.6.24→2025.7.25 诊断事实 + 起病事件；阿昔洛韦乳膏暴露 2025.6.24 | facts 疾病诊断 + events；OCR p5 原文逐字 |
| A8 | "带回剩余糠酸莫米松"仅发布为携回药物记录，未误发布为实际暴露 | fact 携回药物记录（OCR p9）；v9 修复持续有效 |
| A9 | 暴露剂量/单位分离（瑞舒伐他汀 10 mg 等 8 条暴露无单位重复拼接） | medication_exposures_v2 各行 |
| A10 | 事件 12→22 条增长且全部带精度+原文（含 进入导入期/药物发放/胸片 2025-08-08） | clinical_events_v2 |

B. 真正遗漏（原始证据在、当前活动修订缺、按旧修订覆盖情况分级）：

| # | 遗漏 | 原文锚点（OCR p=工作区库页号） | 门禁/原因 | 旧修订覆盖 |
|---|---|---|---|---|
| B1 | **血压 132/96 mmHg**（生命体征值） | p5 "血压132/96mmHg（CS与高血压病史相关）（静息下）"；p6 "血 压:132/96mmHg" | value_unit_date_source 拒绝（fact_908abc5f7 / fact_fad2a5ff1，值串 "132/96"+mmHg） | **任何修订均未发布过**；Profile 仅见 高血压诊断(event+fact)。期望层已标 absent（`expectation:6dee5885…` "测量血压并核实抗高血压药物使用情况"）——损失对复核者可见，但 gap_type=record_incomplete 与事实不符：原始记录完整，属规范化失败，违反"规则判定与缺口原因分离"边界 |
| B2 | **乙肝血清学 4/5 项**：表面抗体 >1000.00阳性(+)、e抗原 <0.05阴性(-)、e抗体 1.55阳性(+)、核心抗体 >4.00阳性(+) | p7 检验报告单表格逐行；邮件 p4 "患者乙肝核心抗体阳性" 佐证 | 12 条单位门禁拒绝中的 4 条（值串含 定性后缀/比较符）；邮件侧候选另因来源语义被拒（fail-closed 正确） | e抗体曾于 d0e3a463、94571fa0(v9) 以干净数值 1.55 IU/mL 发布（本运行模型把定性后缀拼进值串 → **回归**）；核心抗体/表面抗体/e抗原无任何修订发布过。仅表面抗原 阴性(-) 在发布。乙肝排除标准证据链不完整 |
| B3 | HBV-DNA 定性 "未检测到靶基因" IU/mL | p1 乙肝DNA定量表 | 单位门禁（定性文本+单位）；**当前工作树代码下仍会拒绝** → 真合同缺口 | 无任何修订发布 |
| B4 | 心电图电轴 P/QRS/T 46/-4/34 deg；RV5/SV1 0.736/0.561 mV | p4 心电图报告 | 单位门禁（多分量值） | RV5+SV1 总和已发布（A1）；分量/电轴无修订发布 |
| B5 | w22(葎草) sIgE >100.00 kUA/L | p1 sIgE 表；邮件 p4 "秋季过敏原有豚草、艾蒿、葎草、鹅毛草" | 单位门禁（">100.00"） | 无修订发布；其余 8 项 sIgE 已发布 |
| B6 | 2018.09 既往奥马珠单抗 300mg 皮下一次 | p4 "2018.09.uk使用注射用奥马珠单抗，300mg，皮下注射治疗一次" | 单位门禁（整句值+unit=mg；whitelist 也不救） | **无任何修订发布**；2025-04-05 那次已覆盖（A6）。既往生物制剂暴露史缺日期化记录 |
| B7 | 枸地氯雷他定胶囊 8.8mg（2025.4.5-4.19）、孟鲁司特钠片 10mg（2025.4.5-4.12） | p1、p4 病历 | 前者单位门禁（整句值+mg）；后者仅剩 medication_name_incomplete 未解决项（"口服孟"跨页截断） | 枸地曾于 d0e3a463/4ffa83f3 有"药物使用"事实；两药在当前活动修订完全缺席（无事实/事件/暴露） |
| B8 | 糠酸莫米松背景用药**暴露** | 邮件 p4/p5 "目前患者在上午下午均有使用"；p9/p8 佐证真实处方使用 | 候选来源语义标签错标被拒（该文档允许仅 ['unverifiable_source']） | f6fe423a 旧修订 rev3（旧处理修订 complete-529c2876）曾以 unverifiable_source 发布过该暴露 → 管线本可接受弱来源暴露；flag-1（邮件"实际使用直述"能否作暴露来源）**仍待 Codex 裁决**。事实层"糠酸莫米松使用时间不固定"（unverifiable_source）已发布 |

C. 质量观察（不阻断收口判断，但应进入复核/修复清单）：

1. **冲突分组把不同标本的同名分析物配对**：未解决冲突并列展示 WBC 6.01×10⁹/L(血) vs 2.00/μL(尿)、RBC 5.41×10¹²/L(血) vs 1.30/μL(尿)（均 p3）。fail-safe（并列不择优）成立，但分组键缺"标本/检查"维度，产生伪冲突，稀释 5 条冲突高亮的信噪比。
2. **司普奇拜单抗 600mg(2025-04-09) vs 300mg(2025-06-04)** 两次真实先后给药被标为同一"未解决冲突"（exposure:79d00b31 vs exposure:13ec692a，stable_identity 不同）——分组语义需 worker_02 复核。
3. negation 门禁 17 条拒绝中含 IE 相关否认事实（恶性肿瘤病史、严重系统疾病、MG-K10/其他临床试验参与史、滴虫等）；避孕要求已有"生育捐献计划与避孕"覆盖，鼻腔肿瘤有窄口径事实，其余广义否认缺失。是否属门禁正确 fail-closed 或断言对象抽取问题 → worker_02 范围。
4. 未解决项 71 条（record_incomplete 17、ambiguous_date 11、date_range_unclear 9、provenance_followup 5、medication_name_incomplete 3 等），message/reason 字段完整可用。
5. Profile rev5：13 lanes 436 项；待复核 104 = 60 current_due_expectation_gap + 39 weak_source_positive_long_term_history + 5 unresolved_conflict（先前运行 52 → 104 的增量主要来自期望缺口高亮，属合同预期行为）。

**3. 根因（对"有价值的全量重跑"最关键的发现）**

- **观察**：本次单位门禁 12 条拒绝值中，11 条（"132/96"、"46/-4/34"、"0.736/0.561"、">100.00"、">1000.00阳性(+)"、"1.55阳性(+)"、"<0.05阴性(-)"、">4.00阳性(+)" 等）在**当前工作树代码** `_COMPACT_MEASUREMENT_VALUE` 白名单下 fullmatch 通过；仅"未检测到靶基因"仍拒绝。实测：`tests/v2/domain/test_fact_candidate_gates.py` 聚焦 10 项全部通过（0.20s，含 `test_fact_value_unit_accepts_compact_measurement_strings` 的 ("132/96","mmHg") 用例）。
- **观察**：`git diff HEAD` 证实该白名单（及暴露肯定事实支撑规则）是**未提交的工作树改动**（HEAD=411832d 的版本无条件拒绝一切带单位非数值值）。
- **推断（标注为推断）**：运行 916bf32f 的 8910 服务进程加载的是不含白名单的旧门禁代码——即最小通用修复已在工作树就位，但最新一次不可变运行未受益。DB 无 service 启动事件行可确证进程代码版本（既有检查点已有同类"进程跑旧代码"前科：20260904 检查点记录 8910 曾以 v4 模板运行）。
- 推论：**直接全量重跑将原样复现 B1–B5 损失**；重跑前必须验证进程加载了含白名单的代码。剩余真合同缺口仅 B3（定性结果+单位）与 B6/B7（整句值+单位，需结构化建模而非放宽门禁）。
- 来源语义类 44 条拒绝（35 允许['unverifiable_source'] + 9 允许['contemporaneous_objective_result']）：模型标签漂移（gap-2 既有建议仍有效：提示合同公布允许标签词表），属 worker_02/03 的调用链与回归设计范围。

## 工件与证据

- 运行库（只读）：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/enrollment-review-v2.sqlite3`（表：fact_normalization_runs/candidates/gate_results/unresolved_items、clinical_facts/events/exposures_v2、patient_profile_revisions_v2、evidence_expectations_v2、ocr_pages、evidence_locator_artifacts）。
- 运行包：`artifacts/phase5-acceptance/20260905/sar-31001-v11-run-packet.json`、`sar-31001-v12-run-packet.json`（本审计以 v12 为最新）。
- 代码锚点：`app/domain/gates/fact_candidate_gates.py:141-151`（未提交白名单）、`:154-192`（validate_fact_value_unit）、`:408-414`（暴露肯定事实支撑，未提交）；`app/domain/gates/fact_evidence_closure.py:287`（否定门禁）、`:779`（来源语义门禁）；`tests/v2/domain/test_fact_candidate_gates.py:349-377`（白名单回归用例）。
- 上下文：`.trellis/tasks/08-22-phase5-clinical-facts-profile/CHECKPOINT_20260904_FRESH_RUN_FIX_VERIFIED_QC_GAPS.md`（gap-1/gap-2/flag-1 原始定义）、`CHECKPOINT_20260904_PHASE5_HIGH_REASONING_BEFORE_JOB_PAUSED.md`（重跑前 env 契约与验收边界）。
- 本会话零新增文件；未写任何仓库路径。

## 命令与观察记录

- `sqlite3`/python sqlite3（全部 `file:...?mode=ro` + `PRAGMA query_only=ON`）：runs/profiles/candidates/gate_results/unresolved/facts/events/exposures/expectations/ocr_pages/locators 全量只读查询，产出上述清单。
- 值白名单正则复算（python）：11/12 拒绝值 fullmatch 通过，仅"未检测到靶基因"不过。
- `git log/diff/status`（只读）：确认白名单为工作树未提交改动；HEAD 411832d。
- `grep tests/`：定位白名单回归用例已在工作树。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/v2/domain/test_fact_candidate_gates.py -q -p no:cacheprovider -k "value_unit or compact"` → **10 passed**（无 cache/bytecode 副作用）。

## 阻碍或缺失环境

- 无工具/环境阻塞。
- 证据边界 1：原始 PDF 在生产路径（未授权未读）；OCR 层 raw_text 为本审计的原文依据，纸面核对留待 Codex。
- 证据边界 2：无法从 DB 确证 21:27Z 进程加载的代码版本（无 service 启动事件行）——"旧门禁代码"为强推断（白名单通过值被拒 + diff 佐证），非直接观察。

## 重跑请求或下一步

本工作项无需重跑。需 Codex 裁决/交接的精确清单：

1. **重跑前退出门槛（建议）**：确认工作树门禁白名单为预期最小修复后，按 20260904 检查点的显式 env 契约重启 8910，并**实证验证进程代码含白名单**（如以一次单页真实调用观察 "132/96" 类值通过，或核对进程加载文件的哈希），再发起全量不可变运行；`claims_complete` 保持 false，Phase 5 不提前收口，Phase 5.5 不启动。
2. **flag-1（遗留）**：糠酸莫米松暴露——邮件内"实际使用直述"能否作为暴露来源；如收紧，建议按"邮件文档内实际使用直述"建通用来源规则（f6fe423a 已证明管线可发布 unverifiable_source 暴露）。
3. **给 worker_02**：B3（定性结果带单位的通用建模）、B6/B7（整句值→结构化用药记录的提示合同指导）、冲突分组键（标本/检查维度；司普奇拜两次给药误并）、negation 门禁 17 条中 IE 相关否认的语义闭包，均沿共享调用链定位最小项目无关根因。
4. **给 worker_03**：聚焦回归建议——白名单单测已存在并通过；建议补"来源标签词表公布后的事件/暴露候选"回归与"定性结果+单位"fail-closed 用例；重跑验收建议以本报告 B1–B8 作为逐项对照基准，并复核 BP 期望 gap_type=record_incomplete 的归因是否符合"缺口原因分离"边界。
