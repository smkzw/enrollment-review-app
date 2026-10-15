# Codex Execution Plan: enrollment-batch-read-hardening-20260908

Objective: 修订默认关闭的多页实验模块，保证与逐页对照的额度、冻结图片和失败记录可靠；不做真实模型调用

## Work Items

| Worker | Assigned item | Report |
|---|---|---|
| `worker_01` | 只修改app/llm/page_review_batch_experiment.py与tests/test_page_review_batch_experiment.py。初始批额度用route.max_tokens而非乘页数，截断仅翻倍一次。调用前验证所有图片哈希和page身份，按现有read_page方式处理429等待但不换模型，不改默认harness。合成测试覆盖预检、额度、重试、缺页和混页。禁止读病例、env、artifacts、个人harness配置，禁止网络和递归委派。 | `runs/execution/enrollment-batch-read-hardening-20260908/worker_01.md` |

## Manager

No execution manager is dispatched for this route; Codex reviews the worker outputs directly.

## Codex Acceptance

TODO: verify artifacts, tests, source claims, rendered surfaces, blockers, and user-facing completeness.
