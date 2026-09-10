import { describe, expect, it, vi } from "vitest";
import { createPageReviewHttp, decodePageReviewStatus } from "./pageReviewHttp";

const ready = { job_id: "job", state: "completed", review_status: "ready", total_pages: 1,
  accepted_pages: 1, unrelated_pages: 0, failed_pages: 0, pending_pages: 0, can_reread: false };

describe("资料识别接口", () => {
  it("补读用尽仍显示未读清资料，不误报接口异常", () => {
    const result = decodePageReviewStatus({ ...ready, review_status: "needs_reread", accepted_pages: 0, failed_pages: 1 });
    expect(result.reviewStatus).toBe("needs_reread");
    expect(result.canReread).toBe(false);
  });
  it("恢复被拒时保留具体处理建议", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: {
      title: "资料已变更", recovery_action: "请重新发起判读。",
    } }), { status: 409 }));
    await expect(createPageReviewHttp(fetchImpl).resume("s", "e", "j")).rejects.toThrow("资料已变更 请重新发起判读。");
  });
  it("续跑绑定同一任务且不上传来源内容", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({ job_id: "j/1", changed: true })));
    expect(await createPageReviewHttp(fetchImpl).resume("s", "e", "j/1")).toBe("j/1");
    expect(fetchImpl.mock.calls[0][0]).toContain("/page-review-jobs/j%2F1/resume");
    expect(fetchImpl.mock.calls[0][1].method).toBe("POST");
    expect(fetchImpl.mock.calls[0][1].body).toBeUndefined();
  });
  it("工作流结束但失败页尚存时不视为完成", () => {
    const failed = { ...ready, review_status: "needs_reread", accepted_pages: 0, failed_pages: 1, can_reread: true };
    expect(decodePageReviewStatus(failed).reviewStatus).toBe("needs_reread");
    expect(() => decodePageReviewStatus({ ...failed, review_status: "ready" })).toThrow();
  });
  it.each([{ total_pages: 2 }, { pending_pages: -1 }, { total_pages: "1" }, { can_reread: "false" }, { state: "running" }])(
    "拒绝不一致的计数或完成状态 %j", (changes) => {
      expect(() => decodePageReviewStatus({ ...ready, ...changes })).toThrow();
    },
  );
  it("重读请求只提交前驱身份，不提交客户端页内容", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify({ job_id: "child" })));
    const api = createPageReviewHttp(fetchImpl);
    expect(await api.start("s/1", "e/1", "parent")).toBe("child");
    expect(fetchImpl.mock.calls[0][0]).toContain("/subjects/s%2F1/review-episodes/e%2F1/page-review-jobs");
    expect(JSON.parse(fetchImpl.mock.calls[0][1].body)).toEqual({ predecessor_job_id: "parent" });
  });
  it("请求保留取消信号并校验状态", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(new Response(JSON.stringify(ready)));
    const controller = new AbortController();
    expect((await createPageReviewHttp(fetchImpl).status("s", "e", "job", controller.signal)).acceptedPages).toBe(1);
    expect(fetchImpl.mock.calls[0][1].signal).toBe(controller.signal);
  });
});
