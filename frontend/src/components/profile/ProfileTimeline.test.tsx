// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { adaptPatientProfile } from "../../features/patient-profile/model";
import { decodePatientProfileRevision } from "../../api/patient-profile/patientProfileViewModels";
import { makeFactItem, makeLaneSection, makeRevision, PROFILE_LANE_ORDER } from "../../api/patient-profile/patientProfileFixtures";
import { ProfileTimeline, timelineTime } from "./ProfileTimeline";

function modelFor(items: ReturnType<typeof makeFactItem>[]) {
  return adaptPatientProfile(decodePatientProfileRevision(makeRevision({
    lanes: PROFILE_LANE_ORDER.map(lane => makeLaneSection(lane, items.filter(item => item.lane === lane))),
    highlights: [],
  })));
}

describe("分类临床时间线", () => {
  it("默认突出诊疗，基本情况可查看；有界但不精确的时间仍按原范围排序", async () => {
    const model = modelFor([
      makeFactItem({ title: "四月治疗", lane: "medication", start_range: {
        source_text: "4月5日至19日", precision: "unknown", precision_label: "未明确",
        lower_bound: "2026-04-05", upper_bound: "2026-04-19",
      } }),
      makeFactItem({ item_id: "june", source_id: "june-source", title: "六月检查", lane: "test_exam_score", start_range: {
        source_text: "6月", precision: "month", precision_label: "月",
        lower_bound: "2026-06-01", upper_bound: "2026-06-30",
      } }),
      makeFactItem({ item_id: "background", source_id: "background-source", title: "年龄", lane: "demographics" }),
    ]);
    render(<ProfileTimeline model={model} />);
    expect(screen.getByRole("button", { name: "病史与诊疗 2" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: /^年龄/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 4 }).map(node => node.textContent)).toEqual(["4月5日至19日", "2026年6月"]);
    await userEvent.setup().click(screen.getByRole("button", { name: "基本情况与其他记录 1" }));
    expect(screen.getByRole("button", { name: /^年龄/ })).toBeInTheDocument();
    expect(model.items).toHaveLength(3);
  });

  it("月与未知日期保持原精度，不拿记录时间当发生时间", () => {
    const model = modelFor([makeFactItem(), makeFactItem({ item_id: "unknown", source_id: "unknown-source", start_range: null })]);
    expect(timelineTime(model.items[0]!).label).toBe("2026年3月");
    expect(timelineTime(model.items[1]!)).toEqual({ key: "unknown", label: "日期未明确", role: null, sort: null });
    render(<ProfileTimeline model={model} />);
    expect(screen.getByRole("heading", { name: "2026年3月" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "日期未明确" })).toBeInTheDocument();
    expect(screen.queryByText("2026-08-22")).not.toBeInTheDocument();
  });

  it("同日报告与采样分组区别明确，同值同日的两项观察不合并", () => {
    const date = { source_text: "2026-03-01", precision: "day" as const, precision_label: "日", lower_bound: "2026-03-01", upper_bound: "2026-03-01" };
    const model = modelFor([makeFactItem({ title: "采样结果一", start_range: date, date_role: "sampling" }),
      makeFactItem({ item_id: "second", source_id: "source-second", title: "采样结果二", start_range: date, date_role: "sampling" }),
      makeFactItem({ item_id: "report", source_id: "source-report", title: "报告记录", start_range: date, date_role: "report" })]);
    render(<ProfileTimeline model={model} />);
    expect(screen.getAllByRole("heading", { name: "2026-03-01" })).toHaveLength(2);
    expect(screen.getByText("采样日期")).toBeInTheDocument();
    expect(screen.getByText("报告日期")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /采样结果一/ })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: /采样结果二/ })).toHaveAttribute("aria-expanded", "false");
  });

  it("事件点开详情与原件，分类切换后可恢复；不改原始条目或事实数量", async () => {
    const user = userEvent.setup();
    const model = modelFor([makeFactItem({ title: "研究疾病诊断", lane: "target_disease", lane_label: "目标疾病" }),
      makeFactItem({ item_id: "drug", source_id: "drug-source", title: "既往处方", lane: "medication", lane_label: "用药" })]);
    const open = vi.fn();
    render(<ProfileTimeline model={model} onOpenEvidence={open} />);
    const record = screen.getByRole("button", { name: /^研究疾病诊断/ });
    await user.click(record);
    const details = document.getElementById("timeline-detail-item-fact-1")!;
    expect(record).toHaveAttribute("aria-expanded", "true");
    await user.click(within(details).getByRole("button", { name: "查看“研究疾病诊断”的原文证据" }));
    expect(open).toHaveBeenCalledWith(model.items[0]);
    await user.click(screen.getByRole("button", { name: "用药与治疗 1" }));
    expect(screen.queryByRole("button", { name: /^研究疾病诊断/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "全部 2" }));
    expect(screen.getByRole("button", { name: /^研究疾病诊断/ })).toHaveAttribute("aria-expanded", "true");
    expect(model.items).toHaveLength(2);
    expect(model.itemById.has("drug")).toBe(true);
  });

  it("未知日期用途不误标成事件时间，未知枚举拒绝", () => {
    const model = modelFor([makeFactItem({ date_role: "unknown" })]);
    expect(timelineTime(model.items[0]!).role).toBe("原文日期");
    const wire = makeRevision();
    wire.lanes.flatMap(lane => lane.items)[0]!.date_role = "invented" as never;
    expect(() => decodePatientProfileRevision(wire)).toThrow("日期用途");
  });
});
