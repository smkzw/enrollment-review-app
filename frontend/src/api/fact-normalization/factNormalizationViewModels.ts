/**
 * 个例档案整理（事实规范化）任务的严格解码与中文展示投影。
 * 组件只消费中文业务字段；不暴露模型、provider、schema、pipeline 或内部错误码。
 */

export class FactNormalizationDecodeError extends Error {
  readonly name = "FactNormalizationDecodeError";
  constructor(message: string) {
    super(message);
  }
}

export class FactNormalizationApiError extends Error {
  readonly name = "FactNormalizationApiError";
  readonly code: string;
  readonly title: string;
  readonly recoveryAction: string;
  readonly statusCode: number;

  constructor(
    code: string,
    title: string,
    message: string,
    recoveryAction: string,
    statusCode = 0,
  ) {
    super(message);
    this.code = code;
    this.title = title;
    this.recoveryAction = recoveryAction;
    this.statusCode = statusCode;
  }
}

/** 标准 Job 状态机（与 /api/v2/jobs 一致）。 */
export type FactNormalizationJobState =
  | "queued"
  | "running"
  | "completed"
  | "failed_retryable"
  | "failed_final"
  | "cancel_requested"
  | "cancelled"
  | "recovering"
  | "waiting_user";

export interface FactNormalizationCommandView {
  jobId: string;
  runId: string;
  created: boolean;
  state: FactNormalizationJobState;
  stateLabel: string;
  recoveryAction: string;
}

export interface FactNormalizationJobStatusView {
  jobId: string;
  state: FactNormalizationJobState;
  stateLabel: string;
  cancelRequested: boolean;
  progressCompleted: number;
  progressTotal: number;
  recoveryAction: string;
  createdAt: string;
  updatedAt: string;
}

export interface FactNormalizationJobActionView {
  jobId: string;
  state: FactNormalizationJobState;
  stateLabel: string;
  changed: boolean;
}

/** 前端展示用精简相位（不向用户暴露内部枚举名）。 */
export type FactNormalizationDisplayPhase =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "stale";

const JOB_STATES = new Set<string>([
  "queued",
  "running",
  "completed",
  "failed_retryable",
  "failed_final",
  "cancel_requested",
  "cancelled",
  "recovering",
  "waiting_user",
]);

function record(value: unknown, path: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new FactNormalizationDecodeError(`${path} 应为对象。`);
  }
  return value as Record<string, unknown>;
}

function requiredField(row: Record<string, unknown>, key: string, path: string): unknown {
  if (!(key in row)) {
    throw new FactNormalizationDecodeError(`${path}.${key} 缺少字段。`);
  }
  return row[key];
}

function requiredString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new FactNormalizationDecodeError(`${path} 应为非空文字。`);
  }
  return value;
}

function requiredBoolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    throw new FactNormalizationDecodeError(`${path} 应为是非值。`);
  }
  return value;
}

function nonNegativeInteger(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw new FactNormalizationDecodeError(`${path} 应为非负整数。`);
  }
  return value;
}

function jobState(value: unknown, path: string): FactNormalizationJobState {
  const state = requiredString(value, path);
  if (!JOB_STATES.has(state)) {
    throw new FactNormalizationDecodeError(`${path} 不是可识别的任务状态。`);
  }
  return state as FactNormalizationJobState;
}

export function decodeFactNormalizationCommand(payload: unknown): FactNormalizationCommandView {
  const row = record(payload, "command");
  return {
    jobId: requiredString(requiredField(row, "job_id", "command"), "command.job_id"),
    runId: requiredString(requiredField(row, "run_id", "command"), "command.run_id"),
    created: requiredBoolean(requiredField(row, "created", "command"), "command.created"),
    state: jobState(requiredField(row, "state", "command"), "command.state"),
    stateLabel: requiredString(
      requiredField(row, "state_label", "command"),
      "command.state_label",
    ),
    recoveryAction: requiredString(
      requiredField(row, "recovery_action", "command"),
      "command.recovery_action",
    ),
  };
}

export function decodeFactNormalizationJobStatus(
  payload: unknown,
): FactNormalizationJobStatusView {
  const row = record(payload, "task");
  return {
    jobId: requiredString(requiredField(row, "job_id", "task"), "task.job_id"),
    state: jobState(requiredField(row, "state", "task"), "task.state"),
    stateLabel: requiredString(requiredField(row, "state_label", "task"), "task.state_label"),
    cancelRequested: requiredBoolean(
      requiredField(row, "cancel_requested", "task"),
      "task.cancel_requested",
    ),
    progressCompleted: nonNegativeInteger(
      requiredField(row, "progress_completed", "task"),
      "task.progress_completed",
    ),
    progressTotal: nonNegativeInteger(
      requiredField(row, "progress_total", "task"),
      "task.progress_total",
    ),
    recoveryAction: requiredString(
      requiredField(row, "recovery_action", "task"),
      "task.recovery_action",
    ),
    createdAt: requiredString(requiredField(row, "created_at", "task"), "task.created_at"),
    updatedAt: requiredString(requiredField(row, "updated_at", "task"), "task.updated_at"),
  };
}

export function decodeFactNormalizationJobAction(
  payload: unknown,
): FactNormalizationJobActionView {
  const row = record(payload, "action");
  return {
    jobId: requiredString(requiredField(row, "job_id", "action"), "action.job_id"),
    state: jobState(requiredField(row, "state", "action"), "action.state"),
    stateLabel: requiredString(requiredField(row, "state_label", "action"), "action.state_label"),
    changed: requiredBoolean(requiredField(row, "changed", "action"), "action.changed"),
  };
}

export function decodeFactNormalizationError(
  payload: unknown,
  statusCode = 0,
): FactNormalizationApiError {
  if (payload !== null && typeof payload === "object" && "error" in payload) {
    try {
      const error = record(payload.error, "error");
      const code =
        typeof error.code === "string" && error.code.trim().length > 0
          ? error.code
          : "REQUEST_FAILED";
      const title =
        typeof error.title === "string" && error.title.trim().length > 0
          ? error.title
          : "个例档案整理未完成";
      const detail =
        typeof error.detail === "string" && error.detail.trim().length > 0
          ? error.detail
          : "暂时无法整理个例档案。";
      const recoveryAction =
        typeof error.recovery_action === "string" &&
        error.recovery_action.trim().length > 0
          ? error.recovery_action
          : "请稍后重试；若问题持续出现，请联系维护人员。";
      return new FactNormalizationApiError(
        code,
        title,
        detail,
        recoveryAction,
        statusCode,
      );
    } catch {
      // 信封结构损坏：按不可识别错误处理。
    }
  }
  return new FactNormalizationApiError(
    "INVALID_RESPONSE",
    "服务响应异常",
    "个例档案整理服务返回了无法识别的内容。",
    "请稍后重试；若问题持续出现，请联系维护人员。",
    statusCode,
  );
}

export function isTerminalFactNormalizationState(state: FactNormalizationJobState): boolean {
  return (
    state === "completed" ||
    state === "failed_final" ||
    state === "cancelled"
  );
}

export function isFailureFactNormalizationState(state: FactNormalizationJobState): boolean {
  return state === "failed_retryable" || state === "failed_final";
}

/**
 * 将标准任务状态映射为产品要求的五类精简中文相位。
 * `profileStale` 表示档案侧已判定陈旧（资料已更新），优先于任务完成态。
 */
export function factNormalizationDisplayPhase(
  state: FactNormalizationJobState | null,
  options: { profileStale?: boolean } = {},
): FactNormalizationDisplayPhase | null {
  if (options.profileStale === true) return "stale";
  if (state === null) return null;
  if (state === "queued" || state === "waiting_user") return "queued";
  if (state === "running" || state === "recovering" || state === "cancel_requested") {
    return "running";
  }
  if (state === "completed") return "succeeded";
  if (isFailureFactNormalizationState(state) || state === "cancelled") return "failed";
  return null;
}

/** 精简中文状态标题（不展示后端机器值）。 */
export function factNormalizationPhaseTitle(phase: FactNormalizationDisplayPhase): string {
  switch (phase) {
    case "queued":
      return "个例档案整理排队中";
    case "running":
      return "正在整理个例档案";
    case "succeeded":
      return "个例档案已整理完成";
    case "failed":
      return "个例档案整理未完成";
    case "stale":
      return "资料已更新，需重新整理个例档案";
  }
}

/** 具体恢复动作（中文临床措辞）。 */
export function factNormalizationRecoveryHint(
  phase: FactNormalizationDisplayPhase,
  serverRecovery: string | null = null,
): string {
  if (serverRecovery !== null && serverRecovery.trim().length > 0) {
    // 服务端已给中文恢复动作时优先采用，避免前端自造冲突说明。
    return serverRecovery.trim();
  }
  switch (phase) {
    case "queued":
      return "无需操作，排队开始后会自动继续；关闭页面不会中断。";
    case "running":
      return "关闭页面不会中断；可稍后回到本页或受试者档案查看进度。";
    case "succeeded":
      return "可打开受试者档案查看整理结果。";
    case "failed":
      return "请点击「重新整理个例档案」；已完成内容不会重复处理。";
    case "stale":
      return "请点击「重新整理个例档案」按当前已启用资料生成新档案；上一版内容仍可查阅。";
  }
}
