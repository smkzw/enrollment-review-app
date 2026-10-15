# Phase 0 设计

## Baseline Boundary

- Git `main` 的基线提交 `a02b833` 是代码回滚锚点。
- legacy 运行数据和报告不纳入 Git，但通过路径、规模、哈希/mtime 清单保留回归证据。
- V2 代码进入独立命名空间；legacy 服务继续可运行，V2 不复用其写服务。

## Isolation Strategy

1. `app/legacy/` 仅提供显式只读适配入口；旧模块暂不移动以避免基线扰动。
2. 新 repository 默认只接受 V2 storage root/database，不接受 legacy project path。
3. 写保护测试在执行 V2 操作前后比较代表 legacy 文件树快照。
4. 输出、缓存和日志路径分离，投影可以重建，临床源文件和审计记录不可静默覆盖。

## Dependency Gate

每个新依赖记录：官方主页/仓库、精确版本、许可证、维护信号、用途、替代方案、本机兼容性、数据外传和移除方式。Trellis 是开发管理工具，不作为产品运行时依赖。
