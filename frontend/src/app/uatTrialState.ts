/**
 * 中央界面试用状态清单（UAT-P1-13/14 语义）。
 * - 唯一登记入口：所有界面可复位状态必须在此登记，页面不得各自散落键名。
 * - 复位操作只删除登记在册的键（`eligibility-review:uat:` 前缀）：
 *   不执行 sessionStorage.clear()，不做前缀扫描，保留任何未登记键。
 * - 帮助页、任务卡和记录表使用同一个稳定的中文页面版本。
 */

/** 稳定中文页面版本：变更任务语义、示例数据或主要交互时必须显式更新。 */
export const UAT_PAGE_VERSION = "界面试用版 1.5.1";

/** 行动中心的人工确认记录 */
export const UAT_KEY_MANUAL_ACTIONS = "eligibility-review:uat:manual-actions";
/** 从方案新建项目的演示摘要 */
export const UAT_KEY_CREATED_PROJECT = "eligibility-review:uat:created-project";
/** 方案工作台草稿保存状态 */
export const UAT_KEY_PROTOCOL_DRAFT_SAVED =
  "eligibility-review:uat:protocol-draft-saved";
/** 资料整理任务的试用进度 */
export const UAT_KEY_TASK_PROGRESS = "eligibility-review:uat:task-progress";

/** 中央状态清单：新增可复位状态时在此登记，四个页面调用点不得另写键名。 */
export const UAT_TRIAL_STATE_KEYS: ReadonlyArray<string> = [
  UAT_KEY_MANUAL_ACTIONS,
  UAT_KEY_CREATED_PROJECT,
  UAT_KEY_PROTOCOL_DRAFT_SAVED,
  UAT_KEY_TASK_PROGRESS,
];

/** 复位登记在册的全部界面试用状态；只删除清单内的键，不影响其他数据。 */
export function resetUatTrialState(): void {
  for (const key of UAT_TRIAL_STATE_KEYS) {
    try {
      window.sessionStorage.removeItem(key);
    } catch {
      // 浏览器拒绝会话存储时仍可继续当前界面操作。
    }
  }
}
