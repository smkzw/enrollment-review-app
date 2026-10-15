# Phase 0 冻结基线与隔离

## Goal

冻结旧系统可复现基线，建立 V2 目录和写入隔离，完成依赖与许可证决策、资产与清理清单。

## Requirements

- 记录 legacy 的实际运行时、服务端口、依赖状态、测试数量与结果，不沿用过时文档数字。
- 冻结用户决定、会商裁决、关键错误案例、旧项目与报告资产清单及可复现入口。
- 标记 `projects/`、`output/` 和旧报告为 legacy/read-only 回归资产；本阶段不删除临床资产。
- 建立 V2 目录：`frontend/`、`app/api/v2/`、`app/domain/`、`app/workflow/`、`app/storage/`、`app/agents/`、`app/projections/`、`tests/v2/`。
- 建立 legacy/V2 写路径边界和待实现的写保护测试，不让 V2 调用旧项目写 API。
- 对拟采用的开源运行时依赖执行官方来源、版本、许可证、维护状态、兼容性和本机安装路径核验。
- 形成清理候选清单，区分可再生缓存、过程记录、测试输出和临床回归资产；任何删除前保留 manifest。
- 记录当前环境陷阱：legacy 由 `/usr/bin/python3` 运行；其他 Python 环境缺少 FastAPI 不能作为基线。

## Acceptance Criteria

- [x] Git 基线提交存在，可回到重构前状态。
- [x] Legacy 以实际运行时执行 131 项测试全部通过，1 项跳过。
- [x] `/usr/bin/python3 -m compileall` 通过，`/api/health` 返回服务、oMLX、DeepSeek 就绪。
- [x] 冻结清单记录源文件、决定、错误回归案例、运行时与测试证据。
- [x] V2 目录存在，依赖方向有文档和最小导入检查。
- [x] 自动化测试证明 V2 写边界拒绝 legacy 项目与报告路径。
- [x] 依赖决策记录含开源许可证、版本、选择/拒绝理由和回滚方案。
- [x] 清理 manifest 完成；仅清理确认可再生且不承担回归价值的缓存/过程文件。
- [x] Phase 0 独立 checker 验证基线、隔离和清理边界；Codex 已依据测试、锁文件、Git 和健康检查接受。

## Notes

- 本阶段禁止修改临床审核语义、重新跑全量临床项目或删除旧项目。
- Qwen 3.8 不再是本任务会商对象。
