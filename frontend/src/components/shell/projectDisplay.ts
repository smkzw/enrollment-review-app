/**
 * 项目展示名派生（仅显示层，不改变任何领域数据或临床结论）。
 * 示例资料中的内部项目代号与研究期别不得直接出现在可见文案。
 */

import type { ProjectSummaryView } from "../../domain/viewModels";

const PHASE_LABELS: Record<string, string> = {
  phase_i: "Ⅰ期",
  phase_ii: "Ⅱ期",
  phase_iii: "Ⅲ期",
  phase_iv: "Ⅳ期",
};

/** 中文项目展示名示例：界面试用项目 · Ⅲ期 */
export function projectDisplayLabel(project: ProjectSummaryView): string {
  const phase = PHASE_LABELS[project.studyPhase] ?? project.studyPhase;
  return `界面试用项目 · ${phase}`;
}
