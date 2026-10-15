import { expect, it } from "vitest";
import { createPreparedReviewHttp } from "./preparedReviewHttp";

const base = {
  job_id: "workflow", context_id: "context", context_sha256: "a".repeat(64), review_run_id: "run",
  state: "failed_final", state_label: "处理未完成", stage_label: "复核原文依据",
  progress_completed: 1, progress_total: 3, items: [], report_saved: false,
  failure_reason: "方案的资料要求尚未对应到本条件，不需要重复上传原件。", retry_available: false,
};
const read = (value: unknown) => createPreparedReviewHttp(async () => new Response(JSON.stringify(value), {
  status: 200, headers: { "Content-Type": "application/json" },
})).workflow("subject", "screen", "workflow");

it("保留方案侧缺口和不可重试状态，不把它当作病例缺件", async () => {
  const result = await read(base);
  expect(result.failureReason).toContain("不需要重复上传原件");
  expect(result.retryAvailable).toBe(false);
});

it("一般失败仍允许恢复，完成或取消不显示失败原因", async () => {
  expect((await read({ ...base, failure_reason: null, retry_available: true })).retryAvailable).toBe(true);
  for (const state of ["completed", "cancelled"]) {
    const result = await read({ ...base, state, failure_reason: null, retry_available: false });
    expect(result.failureReason).toBeNull();
    expect(result.retryAvailable).toBe(false);
  }
});

it("计算来源核对保留对应候选身份，不冒充审核完成", async () => {
  const task = { job_id: "computation", kind: "computation_input", candidate_job_id: "candidate",
    state: "running", state_label: "正在核对", progress_completed: 1, progress_total: 3 };
  const result = await read({ ...base, state: "running", failure_reason: null, items: [task] });
  expect(result.items[0].kind).toBe("computation_input");
  expect(result.items[0].candidateJobId).toBe("candidate");
  await expect(read({ ...base, items: [{ ...task, candidate_job_id: null }] })).rejects.toThrow();
});

it.each([
  { ...base, retry_available: true },
  { ...base, state: "completed" },
  { ...base, state: "running", failure_reason: null, retry_available: true },
  { ...base, retry_available: "false" },
  { ...base, job_id: "another-workflow" },
])("拒绝矛盾的原因、操作状态和任务身份", async (value) => {
  await expect(read(value)).rejects.toThrow("审核进度暂不能确认");
});
