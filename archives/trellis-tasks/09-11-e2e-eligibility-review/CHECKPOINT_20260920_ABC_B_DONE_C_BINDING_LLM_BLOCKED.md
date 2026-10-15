# CHECKPOINT 2026-09-20：ABC链无损暂停——A✅ B✅ C链机制通、卡模型输出经济性

## 冻结状态（全部真实运行验证，非推演）

### A链（此前已冻结）
- 方案发布：project=draft-project-769ae98f76b4，rule_set rev=1，blocking=0，控制candidate_ready 9候选。

### B链 ✅ 本会话完成（受试者31001，基线节点 6dbf65262bc54f959aaa0a07c783ba52，episode rev=3）
- 5份原件（血常规/筛选期检查报告/病历/乙肝DNA/邮件，源blob在 data_v2/blobs/ 按 source_document_versions_v2.source_blob_sha256 可复取）→ preview 820d3548 → commit → snapshot 503c4b04（24页OCR全succeeded）→ 页级风险核对（用候选attempt_manifest.risk_scan_ids + 实时candidate_event_seq逐页risk-page-reviews，血常规页沿用旧核对prv-8af1ff26即过）→ 元数据确认×5（PATCH /source-document-versions/{id}/metadata，**必须先于build**）→ 完整修订 complete-b9bef521 → 激活 → 双道页判读（job 6b5d8564，24页20接+4复读→reread 954f2662全accepted，review_status=ready，coverage 17bdec46911ce9ac7635bac3b4e7d5cb）→ 判断检索 cd55ecaf（48/48读，12要求结果）→ 归一化 job 513ea77d / run d8064da1（14调用+finalize）**完成**。
- 发布成果：clinical_facts_v2=55条、patient_profile_revisions_v2=1、evidence_expectations_v2=136。
- 页判读双道最终配置：main-A=zhipu直连glm-5.3-flash；main-B=cms-router的MiniMax-M3（PAGE_REVIEW_MAIN_B_PROVIDER=cms-smk BASE=http://127.0.0.1:20128/v1）。

### C链（机制全通，卡在绑定读取的模型输出经济性）
- review-preparation成功：context_id=review-context-v2:378b01d1a4a645fdb4522a9a69777f7d。
- prepared_review_workflow bd2aaace + predicate_binding 4632ba3b + control_binding 434f6d0e：全failed_final。
- 根因（有原件回执实证）：绑定读取要求每原子返回fact_accounting逐事实考虑记录，20原子×55事实≈28万字符输出；双道均finish=length（GLM 24.2万字符、MiniMax 27.8万字符仍截断）。读策略仅翻倍一次至131072。
- 已做未验证的修复（待重跑C链验证）：MAX_SEMANTIC_OUTPUT_TOKENS 131072→262144 + read_candidate_payload翻倍上限随之抬高（page_reader_capabilities.py / predicate_binding_candidates.py）。
- 另一可选方向：fact_accounting记录限长（提示词合同版本化修改，需测试）。

## 本会话通用能力修复（全部与方案/受试者/资料无关，均已带测试）
1. mtplx_deployment_identity 与 mtplx_model_session 外部共享语义一致（external-shared/v1，4测试）。
2. 页判读预检外部共享实例：/health的model_path逐词绑定+vision声明（4测试）。
3. 网关以带前缀id发布模型时按root/name别名匹配（1测试）。
4. 页判读与归一化deepseek道全流式（_streamed_chat_completion，4测试；网关30s非流式504的根治）。
5. 网关流中切换上游模型：放宽为告警记录（deepseek道strict_model_check=False）。
6. 对账胜者与传入顺序解耦（main-A优先，1回归测试）——否则从存储重算选到另一道。
7. 视觉配对伙伴不再要求其键本身被采信（修复单侧采信+对侧歧义时的配对死锁）。
8. 控制来源资料期望显式跳过并留痕（evidence_expectations两处；适用条件接入前的过渡），否则finalize整事务回滚。
9. 归一化小票错误仅记类型进小票、详情进服务日志（守住"小票不带请求细节"既有合同）。

## 环境与启动（后端8902当前运行中，pid 30685→见进程表）
- 后端启动env（沿用即可）：ENROLLMENT_ENV_FILE=$PWD/.env + ENROLLMENT_MTPLX_MODELS_FILE=$PWD/artifacts/mtplx-owned-runtime-20260919/owned-lifecycle-models.json + MTPLX_MEMORY_BUDGET=112G + PAGE_REVIEW_MAIN_B_PROVIDER=cms-smk + PAGE_REVIEW_MAIN_B_BASE_URL=http://127.0.0.1:20128/v1 + PAGE_REVIEW_MAIN_B_MODEL=MiniMax-M3 + PAGE_REVIEW_MAIN_B_API_KEY=<router key> + DECONSTRUCT_BACKEND=glm + PROTOCOL_CONTROL_BACKEND=deepseek + DEEPSEEK_BASE_URL/KEY→路由器 + EVIDENCE_NORMALIZER_PROVIDER=deepseek + EVIDENCE_NORMALIZER_MODEL=cms-deepseek-flash + ENROLLMENT_SEMANTIC_ROUTE_PREFLIGHT=0。
- MTPLX属主清单：artifacts/mtplx-owned-runtime-20260919/owned-lifecycle-models.json（Flash-Next；属主实例对外model id=mtplx-flash-next-optimized-speed；勿再设PAGE_REVIEW_MAIN_B_MODEL覆盖）。
- 已知坑：页判读路由变化后不能局部重读（PAGE_REREAD_NOT_READY）→ 无predecessor全新判读；元数据确认必须在build完整修订之前，否则冻结的是自动建议→重建+全量重判读。

## 下次接手第一步（按序）
1. 重启后端（env同上）。2. retry workflow bd2aaace（或重建prepared-review-workflow，context复用378b01d1）。3. 观察predicate/control绑定是否因262144预算通过；若GLM道对>131072的max_tokens报错，则把main-A道输出上限固定131072、只让MiniMax道放大，或走fact_accounting限长的合同修订。4. 绑定通过后：binding_qualification→judgment_content→qualified-reviews发布→eligibility-review报告→原件回看（GET /subjects/{sid}/evidence-snapshots/{snap}页图比对）。
5. 前端5173（vite经5176）健康；浏览器验收留待C链报告产出后做。
