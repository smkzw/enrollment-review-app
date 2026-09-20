# Codex Execution Plan: enrollment-batched-page-experiment-20260908

Objective: 实现默认关闭的产品多页读片实验适配，复用现有提示及页级校验，仅允许新增独立模块与聚焦测试，不读病例或密钥，不调用被测模型，不修改默认流程。

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 新增app/llm/page_review_batch_experiment.py与tests/test_page_review_batch_experiment.py：把同一节点的一组PageReviewInput经现有build_page_review_messages构造，共用完整ClausePack和Schema，一次图文请求要求按page_artifact_id返回每页原PageReviewPayload；不得自行生成临床题目。复用read_page对拆分响应逐页校验，记录批ID和不同prompt_version/recordID。拒绝混审核节点、重复页或返回未知页；缺页明确失败，不静默丢弃；保留每页失败和有效部分。截断仅按现有规则翻倍一次，不降额度，不修改采样；不能重写已有read_page大文件。使用注入completion和合成数据单测证明页归属、部分失败、未知/重复页、额度与身份。不要读取artifacts/output或任何病例/.env/OMP/Hermes配置。最终报告代码路径、测试、限制。 | `runs/execution/enrollment-batched-page-experiment-20260908/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
