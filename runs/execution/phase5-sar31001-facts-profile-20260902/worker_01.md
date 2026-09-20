# Execution Output: phase5-sar31001-facts-profile-20260902 - worker_01

## Boundary And Context Check

- 按只读任务执行；未调用 `write`/`edit`，未执行任何 POST、PUT、DELETE、模型调用或数据库写入。
- 未启动、停止或修改现有 V2 服务。当前服务已在 `127.0.0.1:8910` 运行，数据库仍可能被其他执行者写入，因此未计算不稳定的数据库最终哈希。
- 未读取 manifest 中记录的生产源目录；仅核对隔离副本、manifest、运行时元数据及正式 HTTP GET 结果。
- 本报告只覆盖运行链路、输入闭包、正式 API 状态和受控后续顺序，不作临床、法规或最终验收结论。

## Work Performed

1. **核对隔离运行库与发布方案**
   - 隔离运行根目录：`artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh`
   - fresh runtime manifest 与输入 manifest 均验证：
     - `copy_verification.verified=true`
     - `source_immutability_verified=true`
   - 旧失败 job ID 被列为禁止复用对象。
   - SAR R16 artifact 记录：
     - deconstruction job：`09b593a721e7430fa72bddf8883f233f`
     - published protocol version：`draft-version-09b593a721e7`
     - EX-07 node-relative lookback interpretation 已形成正式记录
     - 23 条父规则、130 条要求、3 个阶段
     - 隔离服务重算 `publishable=true`，阻塞项为 0。
   - 正式项目 API 已显示该方案实际发布，不能再使用旧 checkpoint 中“尚未发布”的历史状态作为当前判断。

2. **核对 31001 输入闭包**
   - manifest 纳入 5 个 PDF，排除 1 个 `.DS_Store`。
   - 5 个文件均位于隔离副本，并与记录的 SHA-256 一致：
     - `31001-病历.pdf`
     - `31001-基线血常规.pdf`
     - `31001筛选期检查报告单.pdf`
     - `乙肝DNA-31001.pdf`
     - `邮件.pdf`
   - 未发现可直接用于正式处理的额外输入或既有 run artifact。

3. **核对正式 HTTP 链路**
   - 已发布项目存在，subject `31001` 存在。
   - 自动创建了三个审核节点：screening、baseline、run_in。
   - 当前只有 screening 节点有导入资料；baseline 和 run_in 仍为空。
   - screening 的 5 个文件已进入同一 snapshot，OCR 24/24 页完成。
   - OCR 完成不等于 processing revision 可激活：当前 snapshot 仍为 `processing`，active snapshot/revision 均为空。
   - 当前 base processing revision 为 `ready`，但明确 `is_activatable=false`。
   - complete-revision build candidate 当前为 `needs_attention`，job 为 `waiting_user`。
   - 当前未生成 facts、events、exposures、expectations 或 Patient Profile；Profile GET 返回 404“该审核节点还没有生成病历档案”。

4. **形成最小受控继续顺序**
   - 先处理 screening 的 blocking OCR 风险，完成并激活完整 processing revision。
   - 再以相同 hash-verified 五文件、独立 preview/commit/idempotency 和独立 episode authority 处理 baseline。
   - 每个节点只有在 active snapshot 与 active complete processing revision 成对存在后，才能启动 Fact Normalization。
   - Fact Normalization 完成后，再核对同一 authority 下的 facts/events/exposures、expectations、conflicts 和 Profile v2。
   - run_in 默认不处理；这是基于当前发布解释仅覆盖 screening/baseline 的 `[INFERENCE]`，应由有权限的执行者确认后再写入。

## Artifacts And Evidence

- `artifacts/phase5-acceptance/20260901/SAR_R16_NODE_RELATIVE_LOOKBACK_QC_20260902.md`
  - R16 发布前 QC、EX-07 node-relative 解释、publishable 结果。
- `artifacts/phase5-acceptance/20260901/interpretations/sar-ex07-node-relative-lookback-20260902.json`
  - screening 与 baseline 分别使用各自审核节点日期；缺日期时不得借用其他节点日期或结论。
- `artifacts/phase5-acceptance/20260901/manifests/sar-protocol.json`
  - 协议 SHA-256：`075c93b45414dcb4bb33ef1cf623d295a9d8f029d7560ca484a0c0267c4fdabd`
- `artifacts/phase5-acceptance/20260901/manifests/sar-31001.json`
  - 5 个纳入 PDF，全部 copy/source immutability 校验通过。
- `artifacts/phase5-acceptance/20260901/runtime-data/fresh-subject-runtime-contract.json`
  - 约束只能使用 hash-verified immutable manifests。
- `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/runtime-identity.json`
  - fresh DB、marker、禁止复用旧 job/runtime 的约束。
- `artifacts/phase5-acceptance/20260901/runtime-data/sar31001-fresh/runtime/protocol-semantic-route-preflight.json`
  - GLM credential 未配置；MTPLX `127.0.0.1:8002` refused；DeepSeek route reachable；当前为 degraded route。
  - 该文件只证明 protocol semantic route preflight，不能替代 Evidence Normalizer provider/config/endpoint 的独立证明。

当前正式资源：

- project：`draft-project-09b593a721e7`
- subject：`0675cabcc979452dbdd5f5c1570c36d8`
- screening episode：`59b98368e962465ca5d62ff55b4da07d`
- baseline episode：`746385aba80c421ab83aaf439e084b7f`
- run_in episode：`f9548673569b48a499e0f52dfc574f8b`
- screening snapshot：`2685d8e0c0a948ff83a13cb7952eb915`
- screening OCR job：`d55611301d6147abaefbd40ab59b6077`
- base processing revision：`epr-2685d8e0c0a948ff83a13cb7-9b664878b719187d`
- build candidate：`cand-0afbef380e5944dbbc296f10a58d1ef5`
- build job：`514ab32f02544a86b1ae923ac964e541`

## Commands And Observations

```bash
lsof -nP -iTCP:8910 -sTCP:LISTEN
```

观察：Python PID `24777` 监听 `127.0.0.1:8910`。

```bash
ps -p 24777 -o pid=,command=
```

观察：运行命令为：

```text
python 3.12 -m uvicorn app.api.v2.app:create_app --factory --host 127.0.0.1 --port 8910
```

```bash
.venv/bin/python -c 'import platform, sqlite3; print(platform.python_version(), sqlite3.sqlite_version)'
```

观察：

```text
3.12.13 3.53.4
```

```bash
curl -sS http://127.0.0.1:8910/docs
```

观察：HTTP `200`，V2 服务可访问。

```bash
curl -sS http://127.0.0.1:8910/api/health
```

观察：HTTP `404`。V2 没有该 health 路由，不能据此判定服务失败；`/docs` 已返回 `200`。

正式 GET 观察：

- `GET /api/v2/protocol/projects`
  - 返回已发布项目 `MG-K10-SAR`。
- `GET /api/v2/protocol/projects/draft-project-09b593a721e7`
  - 1 个版本，revision `1`
  - protocol version `draft-version-09b593a721e7`
  - SHA 与 protocol manifest 一致
  - `rule_count=23`
  - `publication_count=1`
- `GET /api/v2/projects/draft-project-09b593a721e7/subjects`
  - 返回 subject code `31001`，center `31`。
- `GET /api/v2/subjects/{subject_id}/review-episodes`
  - 返回 screening、baseline、run_in 三个节点；三者当前 active snapshot/revision 均为 `null`。
- screening snapshot GET
  - `status=processing`
  - `is_current=false`
  - 5 个成员
  - collection SHA：`335189bc6bab001497f5c8f46443fca92ac4dddd98cadb6f193d7c7a7fee307f`
- OCR job GET
  - `completed`
  - 24/24 页完成，失败 0。
- base processing revision GET
  - `status=ready`
  - `is_activatable=false`
  - 24 页
  - pending risk flags：`1562`
- candidate GET
  - `status=needs_attention`
  - `complete_revision_id=null`
- build job GET
  - `waiting_user`
  - 0/1 完成。
- baseline snapshot GET
  - `items=[]`
  - active snapshot/revision 均为 `null`。
- screening Patient Profile GET
  - HTTP `404`
  - detail：该审核节点还没有生成病历档案。

OCR 风险聚合：

- date：88 blocking
- decimal_point：363 blocking
- negation_polarity：94 blocking
- numeric_value：942 blocking
- unit：72 blocking
- repeated_text：3 informational

另有：

```text
GET /api/v2/protocol/deconstructions/09b593a721e7430fa72bddf8883f233f/integrity
```

返回：

```json
{
  "publishable": true,
  "blocking_count": 0,
  "issue_codes": [],
  "claims_complete": null,
  "draft_revision_id": null
}
```

`draft_revision_id=null` 与正式 project API 的已发布版本投影不一致；当前应以正式 project API 的 publication/version 结果为发布事实，同时在最终 packet 中保留该 DTO 投影差异。

## Blockers Or Missing Environment

1. **当前硬阻塞：screening 尚未形成可激活的 complete processing revision。**
   - 1562 个 blocking OCR risk flags 仍 pending。
   - candidate 为 `needs_attention`，job 为 `waiting_user`。
   - 因此禁止 activate、Fact Normalization 和 Profile 生成。

2. **baseline 尚未导入。**
   - baseline 节点没有 snapshot，也没有 processing revision。
   - 不能把 screening 的 snapshot、revision、candidate 或 authority 复制到 baseline。

3. **Normalizer 运行环境尚未独立证明。**
   - 当前 semantic route preflight 显示 GLM credential 缺失、MTPLX endpoint refused、DeepSeek 可达。
   - 在实际 normalization 前必须核对 Evidence Normalizer 注册的 PromptVersion/ModelConfig、provider、endpoint、credential 和冻结配置；禁止静默 provider/model 替换。

4. **当前服务仍可能写入数据库。**
   - 不应在服务运行期间导出最终数据库或计算最终 DB hash。
   - packet/export 前需按受控流程停止服务并处理 WAL/SHM。

5. **当前没有完成链路产物。**
   - 未观察到 complete processing revision、published facts/events/exposures、expectations 或 succeeded Profile。
   - `claims_complete` 仍不可视为完成；integrity API 当前返回 `null`，不是通过状态。

## Rerun Requests Or Next Step

以下仅为有权限执行者的最小受控顺序；本 worker 未执行写入：

1. **Screening 风险闭环**
   - 针对每个 blocking flag 做证据支持的 page-level risk review。
   - 使用精确 `scan_id`、`ocr_page_id`、base processing revision、episode expected revision `1`、candidate ID 和当前 expected candidate event seq `2`。
   - 使用 `confirmed_as_read`、`corrected` 或 `not_applicable` 中与证据一致的 decision；每次提供理由和独立幂等键，禁止盲目批量确认。
   - 通过 `POST /api/v2/ocr-pages/{ocr_page_id}/risk-page-reviews` 后反复 GET candidate/job，直到所有 blocking risk、correction、reference、locator、page closure 和 metadata gate 均关闭。

2. **Screening 激活**
   - 仅当 revision 为 `complete`、`ready`、`is_activatable=true` 且 snapshot/revision authority 完全匹配时，调用 activation。
   - 激活后核对 episode 的 active snapshot ID 与 active complete processing revision ID 成对更新，且 snapshot 为 current。

3. **Baseline 独立导入**
   - 用 manifest 中相同的 5 个 hash-verified 隔离文件走正式 preview/commit。
   - 使用 baseline 自己的 episode revision、snapshot、OCR job、processing revision、candidate 和幂等键；不得复用 screening 资源。
   - 按 screening 相同顺序完成 OCR、风险闭环、complete revision 和 activation。

4. **Fact Normalization 与 Profile**
   - 每个节点确认 active snapshot 与 active processing revision 成对存在后，才调用：
     `POST /api/v2/subjects/{subject_id}/review-episodes/{review_episode_id}/fact-normalization-jobs`
   - 服务端会从 active authority 派生输入和配置；轮询 job 至 `succeeded`。
   - 然后分别核对 facts/events/exposures、expectations、conflicts、Profile revision/history，确认没有跨节点引用或空成功。

5. **任何以下情况立即失败关闭**
   - manifest hash/文件数量/范围不一致；
   - OCR 页失败、未闭包或 retryable/permanent failure；
   - candidate 仍 `needs_attention`、存在 pending blocking flag 或未解决引用；
   - activation 后 active snapshot/revision 不成对；
   - authority/config drift、provider 不可达、credential 缺失、静默模型降级；
   - normalizer 空输出、非法结构、页遗漏、伪造 span、跨节点引用或 partial result；
   - Profile 非 `succeeded`、closure 不完整或 GET 仍为 404。

6. 完成上述链路后，停止服务、稳定 WAL/SHM，再由 Codex 进行最终来源哈希、authority chain、独立 QC 和临床/法规验收。
