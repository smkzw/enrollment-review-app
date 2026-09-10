import { describe, expect, it } from "vitest";
import {
  decodePatientProfileRevision,
} from "../../../api/patient-profile/patientProfileViewModels";
import {
  makeRevision,
  PROFILE_LANE_ORDER,
} from "../../../api/patient-profile/patientProfileFixtures";
import {
  adaptPatientProfile,
  formatProfileDateTime,
  locatorsForItem,
  PROFILE_LANE_ORDER as MODEL_LANE_ORDER,
} from "./patientProfileModel";

function required<T>(value: T | undefined, label: string): T {
  if (value === undefined) throw new Error(`测试数据缺少${label}`);
  return value;
}

function adaptWire(wire: ReturnType<typeof makeRevision>) {
  return adaptPatientProfile(decodePatientProfileRevision(wire));
}

describe("adaptPatientProfile", () => {
  it("uses natural Chinese Beijing time for user-facing timestamps", () => {
    expect(formatProfileDateTime("2026-08-22T12:00:00Z")).toBe(
      "2026年8月22日 20:00（北京时间）",
    );
  });
  it("orders 13 lanes in stable display order, keeping empty lanes visible", () => {
    const model = adaptWire(makeRevision());
    expect(model.lanes.map((lane) => lane.lane)).toEqual(MODEL_LANE_ORDER);
    expect(MODEL_LANE_ORDER).toEqual(PROFILE_LANE_ORDER);
    expect(model.lanes).toHaveLength(13);
    // 空泳道仍保留，绝不静默省略临床类别
    const emptyLane = model.lanes.find((lane) => lane.lane === "reproductive");
    expect(emptyLane).toBeDefined();
    expect(required(emptyLane, "生育分区").isEmpty).toBe(true);
    expect(required(emptyLane, "生育分区").items).toHaveLength(0);
    expect(model.itemCount).toBeGreaterThan(0);
  });

  it("exposes the backend highlight set as the only first-screen source", () => {
    const model = adaptWire(makeRevision());
    expect(model.highlights).toHaveLength(1);
    expect(model.highlightedItemIds).toEqual(new Set(["item-fact-1"]));
    expect(model.highlights[0]).toMatchObject({
      itemId: "item-fact-1",
      reasons: ["source_report_abnormal"],
      reasonLabels: ["原报告异常"],
    });
  });

  it("builds locatorById and resolves item deep-link locators", () => {
    const model = adaptWire(makeRevision());
    expect(model.locatorById.has("loc-bp-1")).toBe(true);
    expect(model.locatorById.has("loc-page-1")).toBe(true);
    const fact = required(
      model.lanes.find((lane) => lane.lane === "demographics"),
      "人口学分区",
    ).items[0];
    const locators = locatorsForItem(model, fact);
    expect(locators.map((l) => l.locatorId)).toEqual(["loc-bp-1"]);
    expect(locators[0].bbox).toEqual({ x0: 110, y0: 430, x1: 650, y1: 530 });
  });

  it("groups conflict and expectation items for the page", () => {
    const model = adaptWire(makeRevision());
    expect(model.conflictItems.map((item) => item.itemId)).toEqual([
      "item-conflict-1",
    ]);
    expect(model.expectationItems.map((item) => item.itemId)).toEqual([
      "item-expectation-1",
    ]);
    expect(model.itemById.has("item-fact-1")).toBe(true);
  });

  it("derives generating/failed/stale/empty status semantics", () => {
    expect(adaptWire(makeRevision({ status: "generating" })).isGenerating).toBe(
      true,
    );
    expect(adaptWire(makeRevision({ status: "failed" })).isFailed).toBe(true);
    expect(adaptWire(makeRevision({ status: "stale" })).isStale).toBe(true);

    const emptySucceeded = adaptWire(
      makeRevision({
        lanes: PROFILE_LANE_ORDER.map((lane) => ({
          lane,
          lane_label: lane,
          items: [],
        })),
        highlights: [],
        evidence_locators: [],
      }),
    );
    expect(emptySucceeded.isEmpty).toBe(true);
    expect(emptySucceeded.itemCount).toBe(0);
    // 空态不等于生成中/失败：三种状态相互独立
    expect(emptySucceeded.isGenerating).toBe(false);
    expect(emptySucceeded.isFailed).toBe(false);
  });

  it("does not expose any Phase 6/7 conclusion fields", () => {
    const model = adaptWire(makeRevision());
    for (const forbidden of [
      "eligibility",
      "verdict",
      "actionCount",
      "responsibleParty",
      "pass",
      "fail",
    ]) {
      expect(forbidden in model).toBe(false);
    }
  });
});
