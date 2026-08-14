/**
 * 持久任务事件订阅边界。
 *
 * Phase 2 只提供可复用适配器，不把 Phase 1 合成任务冒充为真实后台任务。
 * 浏览器会用 SSE 的 Last-Event-ID 自动续订；服务端也接受 after_seq，便于
 * 页面从已持久化的最后序号重新建立连接。
 */

export interface PersistentJobEvent {
  seq: number;
  job_event_id: string;
  job_id: string;
  event_type: string;
  step_id: string | null;
  occurred_at: string;
  attempt: number;
  checkpoint_id: string | null;
  retryable: boolean;
  progress_completed: number;
  progress_total: number;
  payload: Record<string, unknown>;
}

export interface PersistentJobDone {
  job_id: string;
  state: string;
  last_seq: number;
}

export interface JobEventSubscription {
  close(): void;
}

export interface SubscribeJobEventsOptions {
  afterSeq?: number;
  baseUrl?: string;
  onEvent(event: PersistentJobEvent): void;
  onDone?(done: PersistentJobDone): void;
  onConnectionError?(): void;
  eventSourceFactory?: (url: string) => EventSource;
}

export function subscribeJobEvents(
  jobId: string,
  options: SubscribeJobEventsOptions,
): JobEventSubscription {
  const base = options.baseUrl ?? "";
  const afterSeq = Math.max(0, options.afterSeq ?? 0);
  const url = `${base}/api/v2/jobs/${encodeURIComponent(jobId)}/events?after_seq=${afterSeq}`;
  const source = (options.eventSourceFactory ?? ((target) => new EventSource(target)))(url);
  const handlePersistentEvent = (message: MessageEvent<string>) => {
    options.onEvent(JSON.parse(message.data) as PersistentJobEvent);
  };

  for (const type of [
    "created",
    "step_started",
    "step_completed",
    "step_failed",
    "retry_scheduled",
    "cancel_requested",
    "cancelled",
    "completed",
    "failed",
  ]) {
    source.addEventListener(type, handlePersistentEvent as EventListener);
  }
  source.addEventListener("done", ((message: MessageEvent<string>) => {
    options.onDone?.(JSON.parse(message.data) as PersistentJobDone);
    source.close();
  }) as EventListener);
  source.onerror = () => options.onConnectionError?.();

  return { close: () => source.close() };
}
