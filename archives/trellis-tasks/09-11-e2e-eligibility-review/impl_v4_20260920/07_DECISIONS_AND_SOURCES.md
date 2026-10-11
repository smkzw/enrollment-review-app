# 决策、证据与不应混淆的层次

## 用户明确要求

2026-09-20本轮答复：云端使用无限制；默认处理少数风险/冲突/未决，全部条款及原件可随时查看；日常几十页到一百余页，扫描检验单（叠加手写批注且未必高清）、病历、手机照片、屏幕翻拍。

既有已决：内置方案Agent、多Agent按职责、跨方案、取消固定全量双VLM/整套ClausePack入每页/统一65K；单Mac单用户；原件及历史不可改；不猜遮盖，不独立诊断波形/影像或重评分；约30分钟只是已发布规则下优化方向。

## 本包工程建议（不是用户曾指定的数字或技术）

角色拆分、source observation/verification分层、例外根因聚合、检索+补查的紧凑关联、初始小额度与动态并发、30/60/120/150页测试层、增加式迁移、候选receipt schema。应在现有实现中映射，不机械创建重复系统。

不要求固定品牌/最新模型、不要求替换OCR供应商、不要求安装LangGraph/向量库，不把自动抽查率或风险数量固定成用户要求。云端许可不等于已有所有云端账户，也不等于允许公开发布病例与密钥。

## 外部文档，仅用于工程核验，不是临床准确性证据

- X01 Google Cloud Document AI / Enterprise Document OCR（2026-09-20访问）：提供文本/版面/手写与质量相关能力；文档提醒质量分可能误报、额外质量评估会增加延迟。支持按风险复用质量信号的设计，不证明任一供应商能准确识别用户真实病例。
  https://docs.cloud.google.com/document-ai/docs/enterprise-document-ocr
- X02 LangChain / LangGraph Persistence（2026-09-20访问）：区分图运行checkpoint和跨运行store，支持恢复与状态管理。仅参考持久化边界；本项目已有runner/JobStore，不因此要求替换框架，也不照搬示例删除临床历史。
  https://docs.langchain.com/oss/python/langgraph/persistence

## GitHub核查与定位原则

本包代码引用固定到同一SHA，函数名为主定位。每一条审阅结论都区分代码确认、局部摘录复现、作者运行记录、待全链验证。GitHub分支检查不代表用户Mac没有未提交修改。

S01–S25为上一轮原报告的固定来源索引；S26–S28为本轮补充/重读。链接列表如下，机器可读版本见sources.json。

- S01: [.trellis/tasks/09-11-e2e-eligibility-review/prd.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/.trellis/tasks/09-11-e2e-eligibility-review/prd.md)

- S02: [app/services/page_review_execution.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/page_review_execution.py)

- S03: [app/llm/page_review_harness.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/page_review_harness.py)

- S04: [app/domain/page_source_association.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/domain/page_source_association.py)

- S05: [.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/.trellis/tasks/09-11-e2e-eligibility-review/AGENT_ASSIGNMENTS_V3_20260917.md)

- S06: [app/llm/predicate_binding_candidates.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/predicate_binding_candidates.py)

- S07: [app/services/predicate_binding_job.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/predicate_binding_job.py)

- S08: [.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260920_ABC_B_DONE_C_BINDING_LLM_BLOCKED.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/.trellis/tasks/09-11-e2e-eligibility-review/CHECKPOINT_20260920_ABC_B_DONE_C_BINDING_LLM_BLOCKED.md)

- S09: [app/llm/page_reader_capabilities.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/page_reader_capabilities.py)

- S10: [app/config.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/config.py)

- S11: [app/services/page_review_job_executor.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/page_review_job_executor.py)

- S12: [app/projections/evidence_expectations.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/projections/evidence_expectations.py)

- S13: [app/services/evidence_expectation_projection_service.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/evidence_expectation_projection_service.py)

- S14: [app/services/frozen_review_calculation.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/frozen_review_calculation.py)

- S15: [frontend/src/pages/EligibilityWorkbenchPage.tsx](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/frontend/src/pages/EligibilityWorkbenchPage.tsx)

- S16: [tests/v2/llm/test_predicate_binding_candidates.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/tests/v2/llm/test_predicate_binding_candidates.py)

- S17: [tests/v2/conftest.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/tests/v2/conftest.py)

- S18: [app/evidence/page_processor.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/evidence/page_processor.py)

- S19: [app/evidence/ocr_adapter.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/evidence/ocr_adapter.py)

- S20: [app/services/prepared_review_workflow.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/prepared_review_workflow.py)

- S21: [app/domain/expression.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/domain/expression.py)

- S22: [app/domain/page_reconciliation.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/domain/page_reconciliation.py)

- S23: [AGENTS.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/AGENTS.md)

- S24: [DOCUMENTS_MAP.md](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/DOCUMENTS_MAP.md)

- S25: [pyproject.toml](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/pyproject.toml)

- S26: [app/services/fact_normalization_source_adapter.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/fact_normalization_source_adapter.py)

- S27: [app/services/page_review_runtime.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/services/page_review_runtime.py)

- S28: [app/llm/page_review_admission.py](https://github.com/smkzw/enrollment-review-app/blob/60f5bb8fe67ac14d44af9ceab0801a9b2a42120b/app/llm/page_review_admission.py)
