/**
 * 事实规范化（整理个例档案）命令与标准任务路径。
 * 路径常量集中在此文件，便于 Codex 在 worker_01 后端路由落地后对齐。
 */

/** POST：仅提交受试者/审核节点与幂等意图；权威元组由服务端派生。 */
export function factNormalizationCommandPath(
  subjectId: string,
  reviewEpisodeId: string,
): string {
  return `/api/v2/subjects/${encodeURIComponent(subjectId)}/review-episodes/${encodeURIComponent(reviewEpisodeId)}/fact-normalization-jobs`;
}

/** GET：标准持久任务状态恢复。 */
export function factNormalizationJobPath(jobId: string): string {
  return `/api/v2/jobs/${encodeURIComponent(jobId)}`;
}

/** POST：仅重试失败范围。 */
export function factNormalizationJobRetryPath(jobId: string): string {
  return `/api/v2/jobs/${encodeURIComponent(jobId)}/retry`;
}

/** 本机持久化 job id，供刷新后恢复；不保存进度本身。 */
export function factNormalizationJobStorageKey(reviewEpisodeId: string): string {
  return `fact-normalization-job:${reviewEpisodeId}`;
}
