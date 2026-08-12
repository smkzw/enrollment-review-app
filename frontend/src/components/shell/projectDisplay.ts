/**
 * 项目展示名派生（仅显示层，不改变任何领域数据或临床结论）。
 * fixture 中的 project_code（如 SYNTHETIC-001-III）与 study_phase
 * （如 phase_iii）不得直接出现在可见文案（用户语言合同：不暴露纯英文项目代号）。
 */

import type { ProjectSummaryView } from "../../domain/viewModels";

const PHASE_LABELS: Record<string, string> = {
  phase_i: "I期",
  phase_ii: "II期",
  phase_iii: "III期",
  phase_iv: "IV期",
};

/** 中文项目展示名：界面试用项目 · III期 */
export function projectDisplayLabel(project: ProjectSummaryView): string {
  const phase = PHASE_LABELS[project.studyPhase] ?? project.studyPhase;
  return `界面试用项目 · ${phase}`;
}
