const LAST_PROTOCOL_JOB_KEY = "enrollment-review:last-protocol-job";

export function rememberProtocolJob(jobId: string): void {
  const normalized = jobId.trim();
  if (normalized.length === 0) return;
  window.localStorage.setItem(LAST_PROTOCOL_JOB_KEY, normalized);
}

export function readRememberedProtocolJob(): string | null {
  const value = window.localStorage.getItem(LAST_PROTOCOL_JOB_KEY)?.trim();
  return value ? value : null;
}

export function clearRememberedProtocolJob(): void {
  window.localStorage.removeItem(LAST_PROTOCOL_JOB_KEY);
}
