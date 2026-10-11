# R01 原子条件与证据对应：待独立审阅输入

## 状态与权限

用户已调整共享会商配置；2026-09-13 重新执行 guard --help 成功，已初始化 r01-semantic-binding-review-20260913-retry，当前 C03 路由为 zcode/zcode/GLM-5.3:max。采用独立会商，是因为原子条件证据对应涉及重大临床解释不确定性。本文仍是审阅输入，不是完成或采纳证明；正式回执和审阅意见由该运行目录保存。不得绕过批准 runner、自行选择模型或递归派发。正式派发须重新核对源文件哈希和工具能力。

唯一工作树为本任务所在的 `.worktrees/phase5-clinical-facts-profile`。审阅只读应用代码、设计与合成反例；不访问私人模型配置、不调用产品模型、不写原件、病例库或应用文件。产品独立模型与工程审阅模型是不同职责。

## 要回答的问题

## 2026-09-13 会商回收

批准 runner 已实际完成 zcode/zcode/GLM-5.3:max 一轮审阅，exit 0，无 fallback；报告在 `runs/conference/r01-semantic-binding-review-20260913-retry/evidence_single_object.md`，原始回执在对应 logs 目录，报告 SHA256 为 `21acaefe72e0095d54f00da2e871e0c6b3bbafb879b39053d57113ebd7d2ac25`。六项审阅源哈希均未变化。主线程再次运行两个相关测试文件：5 passed、2 strict xfailed，2.12秒；已知语义缺陷仍存在。共享配置阻塞已解除，未修改全局配置或产品模型。

主线程核对：组件内资料类型并集仍送给每个触发/例外谓词；V2 转换未传递 asserted_object。采纳补齐对象/来源/绑定版本合同、受试者级有界对应任务与统一求值装配的方向，不把候选索引改名为语义证明。审阅新增“跨资料类别也可证明病史存在”反例待正式登记；其真实临床影响尚未实跑。暂不采纳只封堵例外而保留触发错误的单边终态修复；必须共同修复并保留合法明确结论。下一步按设计§17.1.1落实冻结输入和结构校验，再隔离验证候选生成；正式自动采信仍依既有批准边界。本会商不是临床验收。

从资深临床试验医学监查人员角度审阅设计§17.1.1：如何让上传资料中已经核实的观察，真正对应每个入排原子条件，而不因“同属病史/用药/检验一类”误判条件成立或例外成立？

不得仅建议删除 alias 或把全部结果改为 UNKNOWN。最终须同时保留合法明确结论与未知、冲突、缺判断，并与实时工作台和未来正式审核共用同一求值链。审阅意见不是临床签收或新自动采信算法的接入批准。

## 原始来源和现状

- `docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md` §6.1、§17.1–17.2，尤其§17.1.1，是修复规格，不是已实现声明。
- `docs/REARCHITECTURE_FINAL_DESIGN_20260812.md` 与恢复实施计划 T1/T3/T5，确定方案权威、节点隔离、原文定位和正式记录边界。
- `ENGINEERING_REVIEW_20260912_CODEX.md` 与当前 `docs/PROJECT_CONTEXT.md` 定位已证实问题及近轮修复。
- `app/domain/expression.py` 的 EvaluationContext 与 `_evaluate_atomic`：当前 alias 仍直接参与求值，不能当作语义已验证。
- `app/services/eligibility_review_projection.py`：刚将全局候选词表改为组件内词表，解决不同组件同名属性串用。组件内触发/例外的语义对应仍未闭合。
- `app/domain/contracts/facts.py` 的 supported_requirement_ids、`fact_rule_index.py` 的 FactRuleLink、`review.py` 的 PredicateObservation，各有既定职责，均不可直接改名为已核实的语义绑定。
- `app/domain/gates/assessment.py`：需核对 PredicateObservation 与确定性求值镜像的限制，避免用模型判断伪装为确定性事实。

## 必须区分

1. 资料要求索引与原子条件语义证明。
2. 已发布事实与模型提出的对应候选。
3. 代码可验证的身份/值/单位/日期/来源，与代码不能仅凭结构证明的医学语义。
4. 触发、各条例外、研究者书面判断，各自独立证据。
5. 同一事实合法支持多个条件，与跨对象/跨时点借证。
6. 旧结果可读，与旧绑定在事实校正、规则修订或节点变化后仍可用。

## 反例与要求

`tests/v2/test_predicate_semantic_binding_boundary.py` 中两个 strict xfail 仍表明：任意 clinical_history 经 alias 可证明 condition_present 或 exception_documented。既有确切类型化事实的合法 exists 对照须保留。

`tests/v2/services/test_predicate_candidate_scope.py` 验证当前投影的组件隔离，包含标签更名和顺序交换。这不证明原子条件绑定正确。

审阅须覆盖：触发有证据但例外无证据、真实例外、同事实支持上下界、不同对象同值、部分日期及时间角色、否认范围、跨组件同谓词键、校正后过期绑定、伪造定位、双模型分歧。不要注入 SAR/D001 的药名、阈值、编号或正确答案。

## 期望交付

按严重性列出有代码/设计定位的问题；对§17.1.1给出同意、需改或拒绝及证据。提出最小完整纵向实现顺序，明确冻结输入、候选生产、校验、保存、实时/正式消费各复用哪个现有模块；明确哪些检查只能在隔离双模型和留出集后通过，哪些需要用户批准。不新增调度器，不把建议模块的存在当作接线完成。

## 当前源版本 SHA256

正式审阅前复核；若不同，更新输入后再派发，不能沿用旧验收。

```text
2049586ca93cfe116ab46ee038a0645481d06b9f193ff2ad4f2c6a316427c0b0  app/domain/expression.py
ee9739df4d83beab3b5b8cef5c4432783aa022a3dee69fad64178162e1a22de5  app/services/eligibility_review_projection.py
adf82a004a540e506122963d2a96ef067caaf7afc79d5ecc97dbcaa3c9256891  app/domain/contracts/review.py
de90427a33d87596301aed75ae436b6ea1a66d6cb887ee9bdc6c35447fa8457d  app/domain/contracts/fact_rule_index.py
51df6b7fdae84cd1a8521b1568b8023e00891b0f2bd059a0ecdf1544d771ff9e  docs/REARCHITECTURE_R3_ENGINEERING_DESIGN_20260905.md
24eb8bafc0c1fe5e89bd4b6eab0f1b6eaa840bf8300cb9c3ce0b4c4d339fc6bc  tests/v2/test_predicate_semantic_binding_boundary.py
```
