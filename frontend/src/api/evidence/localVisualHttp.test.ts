import { describe, expect, it } from "vitest";
import { decodeLocalVisualTask } from "./localVisualHttp";

const response = { found: true, candidate_only: true, coverage_scope: "region_only", job_id: "job", state: "completed", configuration_current: true, can_retry: false,
  region: { x0: 1, y0: 2, x1: 20, y1: 30, clockwise_degrees: 90 }, observation_text: "所指对象不明。" };
describe("局部阅读边界", () => {
  it("不把整页或已采信输出接到局部核实", () => {
    expect(decodeLocalVisualTask(response).text).toBe("所指对象不明。");
    expect(() => decodeLocalVisualTask({ ...response, candidate_only: false })).toThrow();
    expect(() => decodeLocalVisualTask({ ...response, coverage_scope: "page" })).toThrow();
    expect(() => decodeLocalVisualTask({ ...response, state: "failed_final" })).toThrow();
    expect(() => decodeLocalVisualTask({ ...response, observation_text: null })).toThrow();
    expect(() => decodeLocalVisualTask({ ...response, observation_text: "  " })).toThrow();
  });
  it("刷新恢复、未完成与没有记录分别显示", () => {
    expect(decodeLocalVisualTask({ ...response, state: "running", observation_text: null }).state).toBe("running");
    expect(decodeLocalVisualTask({ found: false, candidate_only: true, coverage_scope: "region_only" }).found).toBe(false);
  });
  it("拒绝无面积、非整数与未知方向", () => {
    for (const region of [{ ...response.region, x1: 1 }, { ...response.region, y1: 2.5 }, { ...response.region, clockwise_degrees: 45 }]) {
      expect(() => decodeLocalVisualTask({ ...response, region })).toThrow();
    }
  });
});
