全部核对完成。以下为第十三轮审阅报告。

# Conference Output: r05-repeat-binding-review-20260915 - evidence_single_object（第十三轮：辅助观察对应 v3）

## Output

### 一、实际缺陷（均为低严重度）

**AB1（低——单辅助配对多重归属无唯一性约束）**
合同 `observation_relation.py:190-195` 的 `unique_coverage` 只约束 `(auxiliary_pair_id, observation_fact_id)` 键唯一；同一辅助配对可关联多个 owner 事实（不同采集组）——`qualified_observation_relation.py:150-155` 输出多行、`acquisition_group_id` 各异。持续性外部上下文（如持续合并用药关联两次采集）语义合法；单次性测量值的多重归属则是矛盾——合同不区分，且无 `auxiliary_multi_group` 标记。集合语义下无重复计入，但下游按角色过滤时同一辅助事实可进多组证据集。最小修复：消费侧（或 v3.1 输出）为多组归属的辅助配对附 `multi_group: true` 标记，交由角色语义决定；不建议合同层一刀切禁止（误伤持续性上下文）。

**AB2（低——授权历史集合跳过 v19）**
`qualified_binding_selection.py:87` 的 observation 分支允许集为 `{v17, v18, v20}`——上一代 v19 缺席而更旧的 v17/v18 保留。因 `require_observation_method` 强制 `content_consumer_version == v5`（`qualified_observation_relation.py:24-25`），v19 时代的评测记录本就被拒，无绕过路径、方向 fail-closed；但模式不规则（若意图是"最近两代可读"应为 {v18, v19, v20}）。最小修复：确认意图——v19 观察语义视为废弃则维持并加注释，否则补入 v19。

### 二、已核对项（无缺陷，file:line 证据）

- **合同/历史字节**：v1/v2 序列化保持（`observation_relation.py:28-35`）；非 v3 携带辅助拒绝（`:43`）；辅助与 owner 成员不相交（`:44`）、身份必异（`:47`"不能混入其他要求的结果值"）、同 job/frozen/episode/family（`:48-51`）；fact/locator 内容一致性覆盖 `source_members`（`:61-67`）；三辅助字段同存同无（`:184-187`）、排序唯一且键域受控（`:190-195`）、None 省略（`:161-169`）。
- **输入装配（两族对称）**：谓词族按 `predicate_evidence_roles` 只取 `initial_observation`/`preceding_observation` 角色谓词（`observation_relation_input.py:43-55`）；控制族按 `condition_atom_id` 角色映射、限同一 control（`:62-77`）；辅助成员取自**资格任务**配对（非候选准备——`load_completed_candidate_qualification_input`，`:30`）；仅 owner 有配对时建组（`:95`）；coverage 含辅助清单（`:110-111`）；payload `observation-relation-input/v3`（`:116`）。
- **提示与载荷校验**：sources 含 `source_members` 并分列 `observation_pair_ids`/`auxiliary_pair_ids`（`llm/observation_relation.py:29-44`）；schema 将三辅助字段设为 required（`:59-65`）——**新任务必须当前输出**；提示禁止辅助进入 reviewed/origins/links、要求双侧原文、明确"该关联不表示同一指标或允许采用"、notes 分离（`:87-95`）；校验：reviewed 恰为 owner 事实集（`:113-116`）、辅助范围全覆盖且 associations 非 None——**旧回答被拒**（`:119-121`）、双端 (fact, locator) 与摘录逐字核对（`:122-130`）。
- **对账（receipts v3）**：job/summary v3（`:13,:94`）；辅助关联**双路精确交集**（`:63-65`）、争议对称差（`:74`）、无同意关联清单（`:75-76`）；`relationship_graph` 只用 owner links/origins（`:77-78`）——辅助值不进图。
- **资格消费**：辅助资格校验精确到 identity/fact/locator/attribute 且摘录逐字（`qualified_observation_relation.py:72-101`，辅助分支 :75、双端 :140-146）；`qualified_auxiliary` 携带归属组（`:150-155`，`acquisition_by_fact` 覆盖全部 owner 事实 `:133-134`，无 KeyError 面）；辅助不进 `operand_pairs`（`:191-202` 仅 owner 成员）与 `series_constraints` 的日期资格（`:203-209`）；**scope_reasons 不含辅助原因**（`:159-171`），辅助未决/notes/争议/无关联独立输出（`:224-230`）；`clinical_scope_complete/replacement_authorized` 恒 False（`:231`）。
- **版本/闭环**：selection consumer v20 双 Literal（`qualified_binding_selection.py:61,:165`）；observation consumer v5（`qualified_observation_relation.py:12`）——旧评测 fail-closed；`build_observation_relation_messages:49-50` 拒旧版组。

### 三、未完成边界（非缺陷）

辅助归属尚无消费者：目标范围的触发/许可计算（第十二轮已知）、最终复查采用均未接线，`repeat_relation_unverified` 守卫不变；辅助语义方法未评测/审批前不得自动采用；`supplied_scope` 仍只覆盖已供记录，已知缺口另行报告，无全局记录完备声明。全程只读，未运行验证；本报告非临床或产品验收。
