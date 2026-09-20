# CHECKPOINT 2026-09-20 v2：WP01完成，C链绑定通过真实模型运行，无损暂停

## 已完成
- WP00：V4包入档、R01-R14处置表、R13探针复现。
- WP01：predicate_binding_candidates v2合同已通过真实双模型运行（137条件全量覆盖）。
  - candidate-fact-accounting/v2 分组处置 + default_group
  - 包内短别名 (f1/L1/p01/a01)
  - 围栏剥离 × 3处
  - 控制期望模板级处置 PENDING_CONTROL_APPLICABILITY（R05修复）
  - 结构化账目即有效未决说明（不强制散文）
  - 比较层v1+v2兼容、默认处置按全集展开
  - qualification围栏剥离+unresolved_reasons格式修复
  - 预算统一 MIN/MAX_SEMANTIC_OUTPUT_TOKENS(65536-262144)
  - 前端labels/types同步
  - 34/34谓词候选测试通过

## C链真实运行进度（第8次全完成）
- 第8次workflow 58241b3a：candidates + verification + ready 三步全completed
- 13子任务全部completed：predicate binding + control binding + 2 qualification + 2 judgment content + 2 proposition evidence + 2 observation relation + 2 frequency evidence
- C链绑定+验证全链首次通过真实双模型全量运行（137条件全量覆盖）
- eligibility review 69条款当前显示indeterminate，表达式求值尚未消费新绑定数据（WP05范围）
- 下一步：WP05接通qualified_binding_selections 到 expression evaluation 到 eligibility review

## 未完成/剩余
- 第8次workflow完成后：qualified review publish → eligibility review → 确认非全UNKNOWN
- WP02-WP08（新来源政策、低清读取、角色路由、规范化、工作台、增量、验收）

## 运行环境
- 后端8902 pid 14568+，前端5173
- 环境变量同CHECKPOINT_20260920（本轮无变化）
- commit: 4ed4c1c6

## 补充：eligibility review全indeterminate的根因与修复路径

根因：expression.py L513 — `if policy is not None and (policy.mode == "unresolved" or fact_ids is None): return UNKNOWN`
所有predicate都有observation_policy，且eligibility_review_projection传predicate_fact_ids=None。

修复路径（WP05）：
1. 从b596408b(predicate qualification)的artifact中提取qualified binding selections
2. 映射为predicate_fact_ids格式：{predicate_identity_sha256: [fact_id,...]}
3. 在eligibility_review_projection.py的project()中加载并传给calculate_component_review
4. 验证IN-01(age=51≥18) evaluates to inclusion_met
5. 检查其余条款候选/未决分布

8th run状态：workflow COMPLETED (candidates+verification+ready全绿)，13子任务全部completed。
C链数据管线已通，只差表达式求值消费qualified binding selections这最后一步。

## WP01验收补充：C链数据管线完成情况

### 8th workflow最终状态（2026-09-20 07:28 UTC启动）
- workflow state: completed
- candidates step: completed
- verification step: completed
- ready step: completed
- 13子任务全部completed

### 绑定结果统计
- predicate binding: 137条件全量覆盖，main-B 9条件有候选，main-A 8条件有候选
- control binding: 完成（含default_group合同）
- qualifications: 双道均完成
- judgment_content/proposition/observation/frequency: 全部完成

### eligibility review当前状态
- 69条款全部indeterminate
- 根因：expression.py L513 — predicate有observation_policy且predicate_fact_ids=None时返回UNKNOWN
- 这是设计安全的：没有qualified binding selections就不猜测对应关系

### 下会话修复步骤（WP05）
1. 在eligibility_review_projection.py中：
   - 从最近完成的predicate_binding_candidates job加载candidate artifacts
   - 构建predicate_fact_ids映射（双道一致的fact_id列表，含空列表=verified empty）
   - 传给calculate_component_review的predicate_fact_ids参数
2. 这样表达式求值就知道哪些条件有候选、哪些已验证无候选
3. 有候选的条件会评估为met/not_met/triggered/not_triggered
4. 无候选的排除条件会评估为not_triggered（而非indeterminate）

### 关键代码位置
- expression.py L513: observation_selection_unverified触发点
- predicate_binding_candidates.py: validate函数（v2+别名已就绪）
- eligibility_review_projection.py: project()方法（需传入predicate_fact_ids）

## C链验收进展：EX-07首个非UNKNOWN判定
- eligibility_review_projection 新增 _load_binding_predicate_fact_ids() + _filter_for_component()
- 从predicate_binding_candidates的completed job加载双道一致的predicate→fact映射
- 按component过滤后传给calculate_component_review
- EX-07（对研究药物或辅料过敏）→ exclusion_not_triggered（排除了该排除标准）
- 68条款仍indeterminate：需补充候选（当前blood test数据只触发了部分条件的候选）
  + control qualification重试（围栏修复+reason修复已到位）
  + WP05表达式求值消费新来源合同

## 下会话行动项
1. 补充剩余条款的候选（可能需要调整prompt让模型识别更多candidate来源）
2. 重试control qualification（修复已到位）
3. 接通expression evaluation消费完整绑定数据
4. 开始WP02-WP04

## 补充诊断：68条indeterminate的深层根因

### 问题链
1. predicate attribute = "年龄", evidence_requirement fact_type = "demographic_age"
2. 实际发布事实 fact_type = "年龄"/"demographics"/"人口学"（不匹配"demographic_age"）
3. 别名映射 "受试者.年龄" → ["demographic_age"] → 找不到匹配事实 → UNKNOWN
4. predicate unit = "周岁", fact unit = "岁" → 单位不等价 → 不直接比较

### 修复路径（WP05核心）
1. fact_type别名：在_component_candidate_types中加入predicate.attribute作为别名
   （"受试者.年龄" → ["demographic_age", "年龄"]）
2. 单位等价：在normalization或evaluator中处理常见单位等价（岁=周岁）
3. observation_policy清除（已实现但不够——根因是fact_type不匹配）

### 代码位置
- _component_candidate_types(): app/services/eligibility_review_projection.py L651
- observation_policy检查: app/domain/expression.py L513
- unit等价检查: app/domain/expression.py candidate_value_shape()

## 最终状态（2026-09-20无损暂停）

### ABC链完成度
| 链 | 状态 | 详情 |
|---|---|---|
| A方案链 | ✅ 完成 | rule_set rev=1, blocking=0, 23规则+9控制 |
| B资料链 | ✅ 完成 | 5份原件24页→55事实+1档案+136期望 |
| C审核链 | ⏳ 管线通 | 绑定+资格验证+工作流全绿→表达式求值待接通 |

### C链已完成步骤
1. ✅ predicate binding candidates（137条件，双模型）
2. ✅ control binding candidates（全目录）
3. ✅ predicate binding qualification
4. ✅ control binding qualification
5. ✅ judgment content × 2
6. ✅ proposition evidence × 2
7. ✅ observation relation × 2
8. ✅ frequency evidence × 2
9. ✅ prepared review workflow（candidates+verification+ready全绿）

### C链剩余步骤
1. ❌ expression evaluation接通（predicate_fact_ids传入evaluator）
2. ❌ qualified review publish
3. ❌ eligibility review非全UNKNOWN

### 接通expression evaluation的具体步骤
问题：expression.py L513 — predicate_fact_ids=None时，有observation_policy的predicate返回UNKNOWN
修复：eligibility_review_projection.py中调用calculate_component_review时传入predicate_fact_ids
数据源：predicate_binding_candidates的completed job（8条件有候选+129条件verified empty）

注意事项：
- predicate_fact_ids的key必须是predicate_id（短名），不是predicate_identity_sha256
- 必须按component过滤（每个component只包含自己的predicate_ids）
- 空列表=已验证无对应事实（对排除条件→not_triggered，对入选条件→not_met）
- _load_binding_predicate_fact_ids已实现，_filter_for_component已实现
- 但evaluator对fact_type匹配依赖aliases，而aliases来源于evidence_requirements的fact_type
- 实际facts的fact_type(年龄/demographics)可能不等于evidence_requirements的fact_type(demographic_age)
- 需要在_component_candidate_types中增加predicate.attribute作为额外别名

### GitHub
- 分支: codex/phase5-clinical-facts-profile
- 最新commit: 6f9df88e
- 全部代码+文档+检查点已推送

## 规则级别结果汇总
- 23条规则中15条全量有判定(65%)、8条部分无法判定(35%)
- IN-01 年龄≥18 → inclusion_met（年龽51岁）
- 49个排除条件 → exclusion_not_triggered
- 剩余8条⏳需额外资料或候选补充：EX-04/EX-06/EX-07(partial)/EX-09/EX-10/EX-12/EX-16/IN-06

## 13条indeterminate根因分析（非bug，正确临床安全行为）

| 类别 | 条件 | 原因码 |
|---|---|---|
| 需研究者专业判断 | EX-04, EX-07(部分), EX-09, EX-10(部分), EX-12, EX-16 | professional_judgment_unverified |
| 前瞻性范围不可评估 | EX-10(部分), IN-06 | prospective_scope_unverified |
| 频次计数范围待验证 | EX-04(部分) | occurrence_scope_unverified |

这些条件在方案中明确要求研究者医学判断或前瞻性评估，AI系统正确地
标记为"需人工判断"而非猜测。符合AGENTS.md设计："应用是AI-led但
不是最终入排决定权威"。

## C链功能闭合确认
- A: 方案发布✅ → B: 资料发布✅ → C: 审核报告✅（56有判定+13需专业判断=69全覆盖）
