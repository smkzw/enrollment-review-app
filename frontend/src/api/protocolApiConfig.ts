/**
 * 方案解构 V2 API 基址：同源相对路径，开发环境由 Vite 代理至本机 V2 服务。
 */

/** 空字符串表示与页面同源（生产或 preview 同域部署）。 */
export function getProtocolApiBase(): string {
  const configured = import.meta.env.VITE_API_BASE;
  if (typeof configured === "string" && configured.length > 0) {
    return configured.replace(/\/$/, "");
  }
  return "";
}

export const PROTOCOL_DECONSTRUCTIONS_PATH = "/api/v2/protocol/deconstructions";

export function protocolDeconstructionsUrl(suffix = ""): string {
  const base = getProtocolApiBase();
  const path = `${PROTOCOL_DECONSTRUCTIONS_PATH}${suffix}`;
  return base.length > 0 ? `${base}${path}` : path;
}

/** 正式项目读取（重新解构选择与当前正式版本投影）：GET /api/v2/protocol/projects… */
export function protocolProjectsUrl(suffix = ""): string {
  const base = getProtocolApiBase();
  const path = `/api/v2/protocol/projects${suffix}`;
  return base.length > 0 ? `${base}${path}` : path;
}

/** 持久任务操作（当前仅用于从失败步骤重新开始）。 */
export function protocolJobsUrl(suffix = ""): string {
  const base = getProtocolApiBase();
  const path = `/api/v2/jobs${suffix}`;
  return base.length > 0 ? `${base}${path}` : path;
}

/** 构建时显式启用 stub 仓储（组件测试、Playwright 视觉回归）。 */
export function isProtocolWorkbenchStubMode(): boolean {
  return import.meta.env.VITE_PROTOCOL_WORKBENCH_STUB === "true";
}
