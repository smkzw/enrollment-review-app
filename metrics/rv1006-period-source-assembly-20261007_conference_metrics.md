# Conference Metrics: rv1006-period-source-assembly-20261007

Date: 2026-10-07

| Role | Provider | Model | Status | Duration | API calls | Tokens | Result |
|---|---|---|---|---:|---:|---:|---|
| 首轮evidence_single_object | codebuddy-cli | deepseek-v4.1-flash/max | exit0 | 179.212s | 工程CLI内部unknown | unknown | 自动裁短不充分，采用作者字段核对 |
| 同会话实现复核 | codebuddy-cli | deepseek-v4.1-flash/max | exit0 | 137.52s | 工程CLI内部unknown | unknown | 边界认可，共同限定拒修补强 |

## Timeout And Retry Evidence

原session01a11385-586f-7d4e-a832-1d4aadb5cb5c，两轮均无fallback。parent完成等待分别179.1598s、133.278s，不当作模型时长；120分钟静默上限，完成即接续。工具实际报告22/20，第二轮18source+2harness，source访问受限，未运行产品。跟进首次owner引用错误manifest路径exit2、零轮，核实际context manifest后运行成功；不是供应商故障。

## Quality Decision

不把两轮同模型审阅称为两模型共识；不授医学、正式采用或签发权限。最终783软件检查由所有者执行，末次提示/反例晚于独审，实际字段恢复尚待运行。
