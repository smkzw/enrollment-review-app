import { describe, expect, it } from "vitest";
import {
  decodePatientProfileError,
  decodePatientProfileHistory,
  decodePatientProfileRevision,
  PatientProfileApiError,
  PatientProfileDecodeError,
} from "./patientProfileViewModels";
import {
  makeConflictItem,
  makeErrorEnvelope,
  makeEventItem,
  makeExpectationItem,
  makeExposureItem,
  makeFactItem,
  makeHighlight,
  makeHistory,
  makeLaneSection,
  makeLocator,
  makePageOnlyLocator,
  makeRevision,
  PROFILE_LANE_ORDER,
} from "./patientProfileFixtures";

function required<T>(value: T | undefined, label: string): T {
  if (value === undefined) throw new Error(`测试数据缺少${label}`);
  return value;
}

describe("decodePatientProfileRevision", () => {
  it("decodes a complete 13-lane revision into the domain view", () => {
    const view = decodePatientProfileRevision(makeRevision());
    expect(view.schemaVersion).toBe("phase5/v1");
    expect(view.status).toBe("succeeded");
    expect(view.statusLabel).toBe("已生成");
    expect(view.revision).toBe(1);
    expect(view.reviewStage).toBe("screening");
    expect(view.lanes).toHaveLength(13);
    expect(view.lanes.map((lane) => lane.lane)).toEqual(PROFILE_LANE_ORDER);
    expect(view.highlights).toHaveLength(1);
    expect(view.highlights[0]).toMatchObject({
      itemId: "item-fact-1",
      reasons: ["source_report_abnormal"],
      reasonLabels: ["原报告异常"],
    });
    expect(view.evidenceLocators.map((l) => l.locatorId)).toEqual([
      "loc-bp-1",
      "loc-fever-1",
      "loc-page-1",
    ]);
    expect(view.evidenceNavigation.completeProcessingRevisionId).toBe(
      "complete-rev-1",
    );
  });

  it("decodes item sub-shapes (fact/event/exposure/conflict/expectation)", () => {
    const view = decodePatientProfileRevision(
      makeRevision({
        lanes: PROFILE_LANE_ORDER.map((lane) => {
          const item =
            lane === "demographics"
              ? makeFactItem()
              : lane === "symptoms_signs"
                ? makeEventItem()
                : lane === "medication"
                  ? makeExposureItem()
                  : lane === "evidence_quality"
                    ? makeConflictItem()
                    : lane === "test_exam_score"
                      ? makeExpectationItem()
                      : undefined;
          return { lane, lane_label: lane, items: item ? [item] : [] };
        }),
      }),
    );
    const byLane = new Map(view.lanes.map((lane) => [lane.lane, lane]));
    const fact = required(byLane.get("demographics"), "人口学分区").items[0];
    expect(fact.kind).toBe("fact");
    expect(fact.value).toBe("120/80");
    expect(fact.unit).toBe("mmHg");
    expect(fact.polarityLabel).toBe("肯定");
    expect(fact.startRange).toMatchObject({
      precision: "month",
      precisionLabel: "月",
      lowerBound: "2026-03-01",
    });
    const event = required(byLane.get("symptoms_signs"), "症状体征分区").items[0];
    expect(event.kind).toBe("event");
    expect(event.eventType).toBe("symptom");
    const exposure = required(byLane.get("medication"), "药物暴露分区").items[0];
    expect(exposure.kind).toBe("exposure");
    expect(exposure.medicationName).toBe("阿司匹林");
    expect(exposure.dose).toBe("100 mg");
    const conflict = required(byLane.get("evidence_quality"), "资料质量分区").items[0];
    expect(conflict.kind).toBe("conflict");
    expect(conflict.conflictMemberKind).toBe("fact");
    expect(conflict.conflictResolutionRevision).toBe(2);
    const expectation = required(byLane.get("test_exam_score"), "检验检查分区").items[0];
    expect(expectation.kind).toBe("expectation");
    expect(expectation.expectationStatus).toBe("referenced_missing");
    expect(expectation.gapType).toBe("referenced_file_missing");
    expect(expectation.provenanceFollowup).toBe(true);
  });

  it("decodes the four newly surfaced gap types", () => {
    const gapTypes = [
      "observation_unverified",
      "interpretation_conflict",
      "provenance_followup",
      "historical_source_unavailable",
    ] as const;

    for (const gapType of gapTypes) {
      const view = decodePatientProfileRevision(
        makeRevision({
          lanes: PROFILE_LANE_ORDER.map((lane) =>
            lane === "test_exam_score"
              ? makeLaneSection(lane, [
                  makeExpectationItem({
                    item_id: `gap-${gapType}`,
                    gap_type: gapType,
                    gap_type_label: gapType,
                  }),
                ])
              : makeLaneSection(lane, []),
          ),
          highlights: [],
        }),
      );
      const item = required(
        view.lanes.find((lane) => lane.lane === "test_exam_score"),
        "检验检查分区",
      ).items[0];
      expect(item.gapType).toBe(gapType);
    }
  });

  it("rejects an unknown schema version", () => {
    const wire = { ...makeRevision(), schema_version: "phase5/v2" };
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      PatientProfileDecodeError,
    );
  });

  it("rejects an unknown status machine value", () => {
    const wire = { ...makeRevision(), status: "archived" };
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "未知的档案状态 archived",
    );
  });

  it("rejects an unknown lane machine value", () => {
    const base = makeRevision();
    const wire = {
      ...base,
      lanes: base.lanes.map((lane, index) =>
        index === 0 ? { ...lane, lane: "imaginary_lane" } : lane,
      ),
    };
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "未知的泳道 imaginary_lane",
    );
  });

  it("rejects an unknown item kind machine value", () => {
    const base = makeRevision();
    const wire = {
      ...base,
      lanes: base.lanes.map((lane) =>
        lane.lane === "demographics"
          ? { ...lane, items: [{ ...makeFactItem(), kind: "guess" }] }
          : lane,
      ),
    };
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "未知的条目类型 guess",
    );
  });

  it("rejects a lane set that is not exactly the 13 stable lanes", () => {
    const base = makeRevision();
    const wire = {
      ...base,
      lanes: base.lanes.filter((lane) => lane.lane !== "reproductive"),
    };
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "病历档案泳道不完整",
    );
  });

  it("rejects a highlight referencing a nonexistent item", () => {
    const wire = makeRevision({
      highlights: [makeHighlight({ item_id: "no-such-item" })],
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "首屏突出引用了不存在的档案条目 no-such-item",
    );
  });

  it("rejects an item locator that is not resolved in the deep-link set", () => {
    const base = makeRevision();
    const wire = makeRevision({
      lanes: base.lanes.map((lane) =>
        lane.lane === "demographics"
          ? { ...lane, items: [makeFactItem({ locator_ids: ["loc-missing"] })] }
          : lane,
      ),
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "档案条目引用的原文定位没有完整解析：loc-missing",
    );
  });

  it("rejects a bbox locator without authenticity/frame proof", () => {
    const wire = makeRevision({
      evidence_locators: [
        makeLocator({ authenticity: "degraded" }),
        makePageOnlyLocator(),
      ],
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "区域定位缺少真实性证明或原始页坐标系",
    );
  });

  it("rejects a bbox extending beyond the page bounds", () => {
    const wire = makeRevision({
      evidence_locators: [
        makeLocator({ bbox: { x0: 100, y0: 200, x1: 2000, y1: 320 } }),
        makePageOnlyLocator(),
      ],
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "区域定位超出原始资料页范围",
    );
  });

  it("rejects a non-bbox locator carrying region coordinates", () => {
    const wire = makeRevision({
      evidence_locators: [makeLocator(), makeLocator({ precision: "page_only" })],
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "降级定位不得携带区域坐标",
    );
  });

  it("rejects a non-UTC or invalid timestamp", () => {
    const wire = makeRevision({ created_at: "2026-08-22T12:00:00" });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      PatientProfileDecodeError,
    );
  });

  it("allows a null generated_at (generating/failed may lack completion time)", () => {
    const wire = makeRevision({ generated_at: null, status: "generating" });
    const view = decodePatientProfileRevision(wire);
    expect(view.generatedAt).toBeNull();
    expect(view.status).toBe("generating");
  });

  it("rejects a missing required field", () => {
    const { patient_profile_revision_id: omitted, ...wire } = makeRevision();
    expect(omitted).toBe("profile-revision-1");
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "响应缺少字段 revision.patient_profile_revision_id",
    );
  });

  it("rejects a non-finite scalar value", () => {
    const base = makeRevision();
    const wire = makeRevision({
      lanes: base.lanes.map((lane) =>
        lane.lane === "demographics"
          ? { ...lane, items: [makeFactItem({ value: Infinity })] }
          : lane,
      ),
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "响应字段 lanes.items[0].value 应为有限数值",
    );
  });

  it("rejects an empty server label instead of hiding contract drift", () => {
    const wire = makeRevision({ status_label: "" });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "响应字段 revision.status_label 不能为空",
    );
  });

  it("rejects highlight labels that do not correspond one-to-one", () => {
    const wire = makeRevision({
      highlights: [
        makeHighlight({
          item_id: "item-fact-1",
          reasons: ["unresolved_conflict", "current_due_expectation_gap"],
          reason_labels: [],
          gap_type: "source_conflict",
          gap_type_label: "来源冲突",
          detail: "来源冲突待核对",
        }),
      ],
    });
    expect(() => decodePatientProfileRevision(wire)).toThrowError(
      "highlights[0].reason_labels 必须与突出原因逐项对应",
    );
  });
});

describe("decodePatientProfileHistory", () => {
  it("decodes revisions in wire order", () => {
    const view = decodePatientProfileHistory(makeHistory());
    expect(view.subjectId).toBe("subject-1");
    expect(view.reviewEpisodeId).toBe("episode-1");
    expect(view.items.map((item) => item.revision)).toEqual([1, 2]);
    expect(view.items[1].status).toBe("stale");
  });

  it("rejects a history revision that fails strict decoding", () => {
    const base = makeHistory();
    const wire = {
      ...base,
      items: base.items.map((item, index) =>
        index === 0 ? { ...item, lanes: item.lanes.slice(0, 12) } : item,
      ),
    };
    expect(() => decodePatientProfileHistory(wire)).toThrowError(
      PatientProfileDecodeError,
    );
  });
});

describe("decodePatientProfileError", () => {
  it("decodes the error envelope into an ApiError", () => {
    const error = decodePatientProfileError(makeErrorEnvelope(), 404);
    expect(error).toBeInstanceOf(PatientProfileApiError);
    expect(error.code).toBe("NOT_FOUND");
    expect(error.statusCode).toBe(404);
    expect(error.title).toBe("未找到");
    expect(error.message).toContain("还没有生成病历档案");
  });

  it("falls back to INVALID_RESPONSE for a malformed error body", () => {
    const error = decodePatientProfileError({ unexpected: true }, 500);
    expect(error.code).toBe("INVALID_RESPONSE");
    expect(error.statusCode).toBe(500);
  });

  it("uses generic detail when the envelope lacks detail", () => {
    const error = decodePatientProfileError(
      { error: { code: "SERVER_ERROR", title: "失败" } },
      500,
    );
    expect(error.message).toBe("请求未能完成。");
    expect(error.code).toBe("SERVER_ERROR");
  });
});
