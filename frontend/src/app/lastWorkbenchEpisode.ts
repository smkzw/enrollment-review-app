/**
 * 入排工作台最近一次有效审核节点（导航上下文，B4 修复）。
 * - 从全局导航裸进入 /workbench 时恢复最近一次受试者与审核节点，
 *   不静默跳转到其他受试者。
 * - 无效审核节点 URL 不会覆盖此记录：修复地址或裸导航时仍回到最近有效节点。
 * - 只保存导航上下文（ReviewEpisodeId），不保存任何临床事实。
 */

import { UAT_KEY_LAST_WORKBENCH_EPISODE } from "./uatTrialState";
import type { ReviewEpisodeId } from "../domain/ids";

/** 读取最近一次有效审核节点；无记录或存储不可用时返回 null。 */
export function readLastWorkbenchEpisode(): ReviewEpisodeId | null {
  try {
    const saved = window.sessionStorage.getItem(UAT_KEY_LAST_WORKBENCH_EPISODE);
    return saved !== null && saved !== ""
      ? (saved as ReviewEpisodeId)
      : null;
  } catch {
    return null;
  }
}

/** 记录最近一次有效审核节点；存储不可用时静默跳过（不影响当前界面）。 */
export function writeLastWorkbenchEpisode(episodeId: ReviewEpisodeId): void {
  try {
    window.sessionStorage.setItem(UAT_KEY_LAST_WORKBENCH_EPISODE, episodeId);
  } catch {
    // 浏览器拒绝会话存储时仍可继续当前界面操作。
  }
}
