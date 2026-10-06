import { describe, expect, it } from "vitest";
import { decodeLocalVisualTask, decodeLocalFieldComparison, localVisualItemRegion } from "./localVisualHttp";

const response = { found: true, candidate_only: true, coverage_scope: "region_only", job_id: "job", state: "completed", configuration_current: true, can_retry: false,
  region: { x0: 1, y0: 2, x1: 20, y1: 30, clockwise_degrees: 90 }, observation_text: "所指对象不明。" };
const item = { label: "采样时间", raw_value: "2026-01-02", raw_unit: null, reference_text: null, time_label: null,
  annotation_target: null, excerpt: "采样时间：2026-01-02", position: "报告下方", script: "printed", legibility: "clear",
  proposed_bbox: { x0: 200, y0: 200, x1: 800, y1: 800 } };
const localized = { ...response,
  region: { x0: 20, y0: 20, x1: 80, y1: 80, clockwise_degrees: 270, include_context: true, read_format: "localized_candidate" },
  reading_region: { x0: 0, y0: 0, x1: 100, y1: 100, clockwise_degrees: 270, read_format: "localized_candidate" },
  structured_read: { items: [item], unresolved: [] } };
describe("局部阅读边界", () => {
  it("连接失败说明只属于失败记录，不成为读取内容", () => {
    const failed = { ...response, state: "failed_final", observation_text: null,
      can_retry: true, failure_message: "视觉模型连接中断，尚未取得可核实的回答。" };
    expect(decodeLocalVisualTask(failed).failureMessage).toBe(failed.failure_message);
    expect(decodeLocalVisualTask(failed).text).toBeNull();
    for (const override of [{ failure_message: {} }, { failure_message: " " },
      { state: "running" }, { state: "completed", observation_text: "原文" }]) {
      expect(() => decodeLocalVisualTask({ ...failed, ...override })).toThrow();
    }
  });
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
  it("保留明确的周边选项和读取格式，不能把字符串当作已启用", () => {
    const region = { ...response.region, include_context: true, read_format: "localized_candidate" };
    expect(decodeLocalVisualTask({ ...response, region }).region).toEqual(region);
    expect(() => decodeLocalVisualTask({ ...response, region: { ...region, include_context: "true" } })).toThrow();
    expect(() => decodeLocalVisualTask({ ...response, region: { ...region, read_format: "whole_page" } })).toThrow();
  });
  it("逐项位置以实际周边图片为基础；越过圈选一像素也不能裁成有效位置", () => {
    const task = decodeLocalVisualTask(localized);
    expect(localVisualItemRegion(task, task.structuredRead!.items[0])).toEqual({ x0: 20, y0: 20, x1: 80, y1: 80, clockwise_degrees: 270 });
    const outside = decodeLocalVisualTask({ ...localized, structured_read: { items: [{ ...item, proposed_bbox: { ...item.proposed_bbox, x0: 199 } }], unresolved: [] } });
    expect(localVisualItemRegion(outside, outside.structuredRead!.items[0])).toBeNull();
    expect(localVisualItemRegion(task, { ...task.structuredRead!.items[0], proposed_bbox: null })).toBeNull();
  });
  it("拒绝缺来源图片、错误方向、损坏逐项或未完成记录中的项目", () => {
    for (const override of [
      { reading_region: undefined },
      { reading_region: { ...localized.reading_region, clockwise_degrees: 0 } },
      { reading_region: { ...localized.reading_region, x0: 21 } },
      { structured_read: { items: [{ ...item, legibility: "verified" }], unresolved: [] } },
      { structured_read: { items: [{ ...item, proposed_bbox: { ...item.proposed_bbox, x1: 1001 } }], unresolved: [] } },
      { structured_read: { items: [{ ...item, exclusion_triggered: true }], unresolved: [] } },
      { structured_read: { items: [], unresolved: [] } },
      { state: "running", observation_text: null },
    ]) expect(() => decodeLocalVisualTask({ ...localized, ...override })).toThrow();
  });
  it("只有具体疑问也能显示，但无位置不猜测", () => {
    const task = decodeLocalVisualTask({ ...localized, structured_read: { items: [], unresolved: ["字迹不清，无法辨认日期"] } });
    expect(task.structuredRead?.unresolved).toEqual(["字迹不清，无法辨认日期"]);
  });
});

describe("project field comparison", () => {
  const data = { found: true, candidate_only: true, formal_adoption_authorized: false,
    job_id: "field", state: "completed", configuration_current: true, can_retry: false,
    outcome: { item_index: 0, candidate_only: true, source_position_verified: false,
      single_field_transcription_agreement: true, reasons: ["摘录一致，仍需确认归属"] } };
  it("一致只显示候选依据，不冒充已采用", () => {
    expect(decodeLocalFieldComparison(data, 0).outcome?.agreement).toBe(true);
  });
  it.each([
    { formal_adoption_authorized: true }, { candidate_only: false },
    { state: "running" }, { can_retry: true },
    { outcome: { ...data.outcome, item_index: 1 } },
    { outcome: { ...data.outcome, source_position_verified: true } },
    { outcome: null },
  ])("错项、未完成或伪造采信均拒绝 %j", (override) => {
    expect(() => decodeLocalFieldComparison({ ...data, ...override }, 0)).toThrow();
  });
});
