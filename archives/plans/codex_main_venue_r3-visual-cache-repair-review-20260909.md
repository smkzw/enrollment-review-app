# Codex Main-Venue Plan: r3-visual-cache-repair-review-20260909

Date: 2026-09-09
Objective: 只读审阅视觉来源批量核验修复：保存点期间不缓存，缓存构建前后代次一致，定位校验不跨调用跳过；核对回归覆盖及未解决一致性风险，不修改代码或临床数据。

## Task Decomposition

所有者修共享存储边界；单一独立只读节点核保存点失效、构建代次与跨调用定位验证。第二轮核批量预验证后写入及差分，不派平行写入者。

## Source Packet

app/storage/page_review_visual_locator_validation.py、fact_authority.py、evidence_locator_repositories.py、app/services/page_review_visual_sources.py及tests/v2/storage/test_page_review_visual_locator_batch.py。来源为当前代码和回归，不要求医学判读。

## Participant Assignments

| Role | Provider | Model | Output |
|---|---|---|---|
| `evidence_single_object` | `zcode` | `GLM-5.3` | `runs/conference/r3-visual-cache-repair-review-20260909/evidence_single_object.md` |

## Conference Panel Coordination

- No sub-venue chair. Codex leads the assigned panel directly.

## Main-Venue Review

- Codex performs the final synthesis and acceptance.
- This conference mode has no Reasonix second-review role.

## Timeout And Retry Tracking

实际zcode/GLM-5.3:max两轮自然完成，同会话sess_58fe7812-9e11-4783-86c7-89207f51f700，无fallback。673.618秒及220.063秒，均在7200秒等待额度内；原始回执保留logs/conference同名目录。

## Codex Verification Checklist

22项聚焦通过；真实8处来源只读全量与批量覆盖哈希一致，25.860秒/129088查询对3.279秒/17146查询。只接受限定ORM使用边界，不声称解决任意原始SQL保存点、外部identity-map刷新或整例临床验收。
