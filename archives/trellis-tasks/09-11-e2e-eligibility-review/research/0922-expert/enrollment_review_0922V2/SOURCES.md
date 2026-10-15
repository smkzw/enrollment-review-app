# 0922V2 固定版本证据索引

基线 `e7f34d0508c05481164cf13569f66ddf64e2e74f`，前轮 `00c46cbc05eda5ac5ce63909b47de34ee72e18ff`。

- S01 [.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260922_FINAL.md](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/.trellis/tasks/09-11-e2e-eligibility-review/HANDOFF_20260922_FINAL.md) — 完整交接；开发者运行陈述非本轮独立临床验收
- S02 [app/services/eligibility_review_projection.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/services/eligibility_review_projection.py) — 当前作用域查找、配对选择、None回退、实际求值调用
- S03 [app/services/qualified_binding_selection.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/services/qualified_binding_selection.py) — _select_facts_for_identity 与 _select_with_ordering；整条件语义
- S04 [app/domain/expression.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/domain/expression.py) — _evaluate_atomic；空选择UNKNOWN与无选择时旧类别路径
- S05 [app/llm/page_review_harness.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/llm/page_review_harness.py) — 请求构造、失败分类、主记录身份
- S06 [app/llm/page_review_transport_options.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/llm/page_review_transport_options.py) — opencode-go 当前返回空 options
- S07 [scripts/build_scale_validation_set.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/scripts/build_scale_validation_set.py) — 默认路径、作用域、媒体页数与解码
- S08 [scripts/run_scale_validation.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/scripts/run_scale_validation.py) — 错误处理改善、剩余分母/范围/完整链问题
- S09 [scripts/wp08_muse_spark_watch.sh](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/scripts/wp08_muse_spark_watch.sh) — 明文移除；环境读取顺序、健康判定、终态
- S10 [frontend/src/pages/EligibilityWorkbenchPage.tsx](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/frontend/src/pages/EligibilityWorkbenchPage.tsx) — unused变量、问题分组、成员排序、原件浏览、版本
- S11 [frontend/src/styles/workbench.css](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/frontend/src/styles/workbench.css) — 1:1.1:1.1 列宽与无marker的分块条目
- S12 [frontend/tsconfig.app.json](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/frontend/tsconfig.app.json) — noUnusedLocals/noUnusedParameters=true
- S13 [frontend/package.json](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/frontend/package.json) — build=tsc -b && vite build；声明 TS 7.0.2
- S14 [app/services/fact_correction_service.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/services/fact_correction_service.py) — 同对象+共享定位只是相关候选，尚不是同观察证明
- S15 [app/domain/contracts/predicate_binding.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/domain/contracts/predicate_binding.py) — 冻结输入全局谓词ID唯一性，排除误报
- S16 [app/services/page_review_job_service.py](https://github.com/smkzw/enrollment-review-app/blob/e7f34d0508c05481164cf13569f66ddf64e2e74f/app/services/page_review_job_service.py) — 逐页固定A/B步骤仍在正式计划器

外部标准/处理依据（非模型能力验收）：
- HTTP 400/413语义：https://www.rfc-editor.org/rfc/rfc9110.html
- 凭据轮换优先：https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository

不从公开文档声称用户当前账户额度、模型端点可用性或模型权重身份已经验证。
