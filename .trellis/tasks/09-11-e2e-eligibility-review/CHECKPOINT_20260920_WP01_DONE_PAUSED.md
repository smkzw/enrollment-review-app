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
