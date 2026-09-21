# CHECKPOINT 2026-09-21：P0安全修复完成

## 修复内容（对应V4 followup审阅ER-01至ER-05）

### A1 ✅ expression.py空选择→UNKNOWN
- 撤回verified_no_matching_fact→FALSE
- 空候选/无合格事实→UNKNOWN（提取层状态≠临床FALSE）
- 34/34谓词候选测试通过

### A2 ✅ 删除blanket has_binding绕过
- eligibility_review_projection: 移除has_binding→expectations=[]和source_gaps=∅
- component_review: 移除predicate_fact_ids→批量移除RECORD_INCOMPLETE等gaps
- 现在gap derivation始终基于实际证据和expectations

### A3 ✅ binding selection作用域修复
- _load_binding_predicate_fact_ids按project/subject/episode过滤
- 不再全库查询最新任务（防止跨受试者干扰）
- 不使用blanket except-return-None静默伪装

### 保留的安全改进（非回退）
- v2分组处置合同+短别名（解决O(P×F)输出爆炸）
- 围栏剥离×3处
- 单位等价映射（岁=周岁）
- 控制期望模板级处置（PENDING_CONTROL_APPLICABILITY）
- 枚举repair（invalid values→safe fallback）
- R13定位去重修复
- R14元数据自动采用（可识别类型不再阻断）
- SourcePolicy合同

### 当前ABC状态
- A✅发布，B✅发布，C: binding+qualification数据管线完成
- eligibility review: 按正确语义评估（部分indeterminate是正确的安全行为）
- 下一步：正确接入qualified binding selections→非全UNKNOWN→WP03-WP08
