// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { adaptPatientProfile } from "../../features/patient-profile/model";
import { decodePatientProfileRevision } from "../../api/patient-profile/patientProfileViewModels";
import { makeFactItem, makeLaneSection, makeRevision, PROFILE_LANE_ORDER } from "../../api/patient-profile/patientProfileFixtures";
import { ProfileTimeline, timelineTime, clinicalSpan } from "./ProfileTimeline";

function modelFor(items: ReturnType<typeof makeFactItem>[]) {
  return adaptPatientProfile(decodePatientProfileRevision(makeRevision({
    lanes: PROFILE_LANE_ORDER.map(lane => makeLaneSection(lane, items.filter(item => item.lane === lane))), highlights: [],
  })));
}
const date = (value: string) => ({ source_text: value, precision: "day" as const, precision_label: "日", lower_bound: value, upper_bound: value });

describe("交互式临床时间图", () => {
  it("按病史／用药画点；正常检查、行政信息和明确否认不铺在主图", () => {
    const model = modelFor([
      makeFactItem({ lane: "target_disease", asserted_object: "研究疾病", title: "研究疾病" }),
      makeFactItem({ item_id: "drug", source_id: "drug-source", lane: "medication", asserted_object: "药物甲", title: "药物甲" }),
      makeFactItem({ item_id: "normal", source_id: "normal-source", lane: "test_exam_score", title: "正常检查" }),
      makeFactItem({ item_id: "background", source_id: "background-source", title: "年龄" }),
      makeFactItem({ item_id: "denial", source_id: "denial-source", lane: "medical_history", asserted_object: "无此病史", polarity: "negated" }),
    ]);
    const { container } = render(<ProfileTimeline model={model} />);
    expect(screen.getByRole("region", { name: "病史与诊断时间图" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "用药与治疗时间图" })).toBeInTheDocument();
    expect(container.querySelectorAll(".clinical-chart__point")).toHaveLength(2);
    expect(screen.queryByText("正常检查")).not.toBeInTheDocument();
    expect(screen.queryByText("年龄")).not.toBeInTheDocument();
    expect(screen.queryByText("无此病史")).not.toBeInTheDocument();
    expect(model.items).toHaveLength(5);
  });

  it("同对象多次记录归一行但保留各个点，重叠点错开且不合并独立记录", () => {
    const model = modelFor([makeFactItem({ lane: "medication", asserted_object: "药物甲", start_range: date("2026-03-01") }),
      makeFactItem({ item_id: "second", source_id: "source-second", lane: "medication", asserted_object: "药物甲", start_range: date("2026-03-01") })]);
    const { container } = render(<ProfileTimeline model={model} />);
    expect(container.querySelectorAll(".clinical-chart__row")).toHaveLength(1);
    const points = [...container.querySelectorAll<HTMLButtonElement>(".clinical-chart__point")];
    expect(points).toHaveLength(2);
    expect(points[0]!.style.top).not.toBe(points[1]!.style.top);
  });

  it("月范围不是持续用药区间，未知日期不拿记录时间补", () => {
    const model = modelFor([makeFactItem({ lane: "medication" }),
      makeFactItem({ item_id: "unknown", source_id: "unknown-source", lane: "medical_history", start_range: null })]);
    const medication = model.items.find(item => item.lane === "medication")!;
    expect(timelineTime(medication).label).toBe("2026年3月");
    expect(clinicalSpan(medication)).toMatchObject({ uncertain: true, interval: false });
    const unknown = model.itemById.get("unknown")!;
    expect(clinicalSpan(unknown)).toBeNull();
    const { container } = render(<ProfileTimeline model={model} />);
    expect(container.querySelector(".clinical-chart__point")).toHaveClass("is-range", "is-uncertain");
    expect(container.querySelector(".clinical-chart__point")).not.toHaveClass("is-interval");
    expect(screen.getByRole("button", { name: /日期未明确/ })).toBeInTheDocument();
    expect(screen.queryByText("2026-08-22")).not.toBeInTheDocument();
  });

  it("点击图点下钻详情和原件，关闭详情不会删记录", async () => {
    const model = modelFor([makeFactItem({ title: "研究疾病诊断", asserted_object: "研究疾病诊断", lane: "target_disease" })]);
    const open = vi.fn();
    render(<ProfileTimeline model={model} onOpenEvidence={open} />);
    await userEvent.click(screen.getByRole("button", { name: /^研究疾病诊断，/ }));
    const details = screen.getByRole("complementary", { name: "临床记录详情" });
    await userEvent.click(within(details).getByRole("button", { name: "查看“研究疾病诊断”的原文证据" }));
    expect(open).toHaveBeenCalledWith(model.items[0]);
    await userEvent.click(screen.getByRole("button", { name: "关闭记录详情" }));
    expect(screen.queryByRole("complementary", { name: "临床记录详情" })).not.toBeInTheDocument();
    expect(model.items).toHaveLength(1);
  });

  it("只显示明确异常，未知参考范围不当作正常或异常", () => {
    const model = modelFor([makeFactItem({ lane: "test_exam_score", title: "偏高项目", asserted_object: "偏高项目", reference_abnormality: "high" }),
      makeFactItem({ item_id: "normal", source_id: "normal-source", lane: "test_exam_score", title: "正常项目" }),
      makeFactItem({ item_id: "low", source_id: "low-source", lane: "test_exam_score", title: "偏低项目", asserted_object: "偏低项目", reference_abnormality: "low" })]);
    render(<ProfileTimeline model={model} />);
    expect(screen.getByText("高于参考上限")).toBeInTheDocument();
    expect(screen.getByText("低于参考下限")).toBeInTheDocument();
    expect(screen.queryByText("正常项目")).not.toBeInTheDocument();
    expect(model.items).toHaveLength(3);
  });

  it("近一年只是可切换的视图范围，更早记录仍可恢复", async () => {
    const model = modelFor([makeFactItem({ lane: "medication", asserted_object: "既往治疗", start_range: date("2018-03-01") }),
      makeFactItem({ item_id: "recent", source_id: "recent-source", lane: "medication", asserted_object: "近期治疗", start_range: date("2026-03-01") })]);
    render(<ProfileTimeline model={model} />);
    const chart = screen.getByRole("region", { name: "用药与治疗时间图" });
    await userEvent.click(within(chart).getByRole("button", { name: "近一年" }));
    expect(within(chart).queryByText("既往治疗")).not.toBeInTheDocument();
    await userEvent.click(within(chart).getByRole("button", { name: "查看更早的 1 条记录" }));
    expect(within(chart).getByText("既往治疗")).toBeInTheDocument();
  });

  it("未知枚举拒绝；日期角色不改写为发生时间", () => {
    const model = modelFor([makeFactItem({ date_role: "unknown" })]);
    expect(timelineTime(model.items[0]!).role).toBe("原文日期");
    const wire = makeRevision();
    wire.lanes.flatMap(lane => lane.items)[0]!.reference_abnormality = "invented" as never;
    expect(() => decodePatientProfileRevision(wire)).toThrow("参考范围异常");
  });
});
