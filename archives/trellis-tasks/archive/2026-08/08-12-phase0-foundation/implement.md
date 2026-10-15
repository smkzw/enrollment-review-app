# Phase 0 实施步骤

1. 生成 `docs/v2/phase0/BASELINE_MANIFEST.md`，记录 Git、运行时、测试、服务和资产规模。
2. 生成 `docs/v2/phase0/DECISION_AND_REGRESSION_INDEX.md`，索引冻结决定和典型错误案例。
3. 生成 `docs/v2/phase0/DEPENDENCY_DECISIONS.md`，完成开源依赖两轮核验。
4. 生成 `docs/v2/phase0/CLEANUP_MANIFEST.md`，先列清单和保留理由，再做有限清理。
5. 创建 V2 目录与说明文件，加入最小导入/依赖方向检查。
6. 加入 legacy 文件树快照与写保护测试。
7. 重跑 legacy 基线、V2 最小测试和健康检查，交由独立 checker 审查。
