import { describe, expect, it, vi } from "vitest";

import { subscribeJobEvents } from "./jobEvents";

class FakeEventSource {
  readonly listeners = new Map<string, EventListener>();
  onerror: ((event: Event) => void) | null = null;
  close = vi.fn();

  addEventListener(type: string, listener: EventListener): void {
    this.listeners.set(type, listener);
  }

  emit(type: string, data: object): void {
    this.listeners.get(type)?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

describe("持久任务事件订阅", () => {
  it("携带最后序号并转发持久事件", () => {
    const source = new FakeEventSource();
    const onEvent = vi.fn();
    let openedUrl = "";
    subscribeJobEvents("job/一", {
      afterSeq: 7,
      onEvent,
      eventSourceFactory: (url) => {
        openedUrl = url;
        return source as unknown as EventSource;
      },
    });

    source.emit("step_completed", { seq: 8, job_id: "job/一" });
    expect(openedUrl).toBe("/api/v2/jobs/job%2F%E4%B8%80/events?after_seq=7");
    expect(onEvent).toHaveBeenCalledWith({ seq: 8, job_id: "job/一" });
  });

  it("收到完成事件后关闭连接", () => {
    const source = new FakeEventSource();
    const onDone = vi.fn();
    subscribeJobEvents("job-1", {
      onEvent: vi.fn(),
      onDone,
      eventSourceFactory: () => source as unknown as EventSource,
    });

    source.emit("done", { job_id: "job-1", state: "completed", last_seq: 9 });
    expect(onDone).toHaveBeenCalledOnce();
    expect(source.close).toHaveBeenCalledOnce();
  });
});
