# review_index字段说明

该JSON是交接索引，不是产品合同。没有发生的运行无需捏造条目；有事实就填对应数组。复制模板后将 `document_kind` 改为 `handoff`，填写带时区 `recorded_at` 与实际交付代码快照。

## 核心条目

### code_snapshots

`id`（如CODE-01）、`kind`（commit/working_tree）、`base_commit`（40位SHA）、`access`（reviewer_accessible/local_only/not_provided）。

commit表示该代码状态由该提交确定；working_tree还需 `manifest_artifact_id` 指向涉及执行的源码/测试/依赖配置及必要未跟踪模块的净化文件哈希清单。整个临床数据目录不进入清单。代码快照是否实际可取得须人工验证，索引不能自证。

### changes

`id`、`paths`、`purpose`、`delivery_state`（committed/patch_attached/local_only/planned）、`evidence_ids`。不要把planned写成已实现。补丁仅作为可审阅输入，不自动授权应用。

### claims

`id`、`statement`、`status`（static_observation/reproduced/verified/author_report/unverified/refuted）、`evidence_ids`、`test_ids`、`limitations`；运行性结论还须 `snapshot_id`。verified/reproduced必须有实际执行测试索引；仅静态阅读使用static_observation。limits写局部到哪层、没有证明什么。

### tests

`id`、`snapshot_id`、`execution_kind`（command/product_entry）、`command`、`status`（passed/failed/interrupted/blocked/not_run）、`exit_code`（未运行null）、`counts`（passed/failed/skipped，缺日志null）、`evidence_ids`。

命令记录真实进程退出码；直接产品API/界面操作没有进程退出码时填null，并记录 `expected_result` 和 `actual_result`，不为凑格式捏造exit=0。

补充字段可包括：cwd去敏别名、开始结束时间及时区、依赖/运行环境、fixture版本、数据类别、运行入口、expected/actual、model/request/response/usage/timing。缺报不能填零。运行的测试必须关联实际快照，不能仅填当前HEAD。

### artifacts

`id`、`path`（仓库相对路径、附件名或受控本地别名）、`sha256`（有字节才填；可null）、`access`（reviewer_accessible/local_only/missing/not_provided）、`sensitivity`（public_technical/redacted/restricted_source）。

restricted_source不得标为普通审阅包可访问；确有特殊授权则通过单独受控途径交付，并在正文说明，本轻量索引默认按local_only处理。切勿在JSON中放API凭据、患者身份、原始病历正文或含token的URL。

### hypotheses

`id`、`statement`、`support_evidence_ids`、`counter_evidence_ids`、`alternatives`（列表）、`disconfirming_test`。没有反证不代表已证明；缺依据可明确写未取得。

### recommendations

`id`、`proposal`、`decision_status`（approved/proposed/rejected）、`basis`、`risk`、`validation`。已批准的R1和D-0929-01可引用；新建议不能擅自标approved。

### next_actions

`id`、`action`、`depends_on`、`deliverable`、`authorization_boundary`；最多3条。明确哪些可并行，不写下一步无限任务目录。

## 一个正确表达方式（教学示例，非真实结果）

不写：“308项通过，表格已修好。”

可写：“T-01在CODE-01的合成一格多段用例通过；E-01是原日志。本轮未在真实deep2和工作稿消费者验证，CLAIM-01仅覆盖结构层。”

不写：“原文没有足够信息，所以唯一安全动作是继续补问模型。”

可写：“H-01可能是原文范围歧义；替代解释是渲染漏表头。用原DOCX与渲染逐格对照可排除后者；若不能排除，不作临床解释结论。”

不写：“本机路径已附，外部审阅已可重现。”

可写：“E-02受控本地可读，当前外部不可读；公开同构夹具E-03只证明结构机制，不代替原件审核。”
