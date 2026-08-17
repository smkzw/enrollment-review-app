/**
 * 方案重新解构并列差异 ViewModel：八类结构化差异的展示模型。
 * 展示层只消费这里定义的结构，不解析自由文本推导临床语义。
 */

export type DiffCategoryKey =
  | "added"
  | "removed"
  | "original_text"
  | "logic"
  | "time_window"
  | "exception"
  | "evidence"
  | "due_stage";

export interface ProtocolCategoryChangeView {
  /** 八类中该类别的稳定键 */
  category: DiffCategoryKey;
  categoryLabel: string;
  /** 稳定引用：父规则用官方编号，子组件用展示编号（如 IN-01a） */
  stableRef: string;
  kind: "rule" | "component" | "requirement";
  previous: unknown;
  current: unknown;
}

export interface ProtocolRuleDiffView {
  officialCode: string;
  /** 整条父规则：新增/删除的稳定说明 */
  added: boolean;
  removed: boolean;
  addedComponentRefs: string[];
  removedComponentRefs: string[];
  /** 六类子组件级变化（原文/逻辑/时间窗/例外/证据要求/应完成阶段） */
  changes: ProtocolCategoryChangeView[];
  /** 该父规则是否存在任何差异（含新增/删除） */
  hasChanges: boolean;
}

export interface ProtocolDraftDiffView {
  /** 新增的整条父规则编号 */
  addedRuleCodes: string[];
  /** 删除的整条父规则编号 */
  removedRuleCodes: string[];
  /** 有修改的整条父规则编号 */
  modifiedRuleCodes: string[];
  /** 逐条父规则的八类差异详情 */
  ruleDiffs: ProtocolRuleDiffView[];
}
