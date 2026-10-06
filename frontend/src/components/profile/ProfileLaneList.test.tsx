// @vitest-environment jsdom
/**
 * ProfileLaneList：13 条泳道稳定顺序展示；空泳道保留并说明“是否构成资料缺口由覆盖决定”。
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  adaptPatientProfile,
  PROFILE_LANE_ORDER,
} from "../../features/patient-profile/model";
import {
  decodePatientProfileRevision,
} from "../../api/patient-profile/patientProfileViewModels";
import {
  laneLabelFor,
  makeLaneSection,
  makeFactItem,
  makeEventItem,
  makeRevision,
} from "../../api/patient-profile/patientProfileFixtures";
import { ProfileLaneList } from "./ProfileLaneList";

describe("ProfileLaneList", () => {
  it("普通报告行政信息不挤占正文，临床内容、研究者判断及原始索引保留", () => {
    const fields = ["报告医师", "申请医生", "第１页／共１页", "血压", "白细胞计数",
      "报告日期", "用药开始日期", "研究者书面判断", "报告医师判断异常有临床意义"];
    const facts = fields.map((field, index) => makeFactItem({
      item_id: `fact-${index}`, source_id: `source-${index}`, title: `记录${index}`,
      asserted_object: field, locator_ids: [], requirement_ids: [],
    }));
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision({
      lanes: PROFILE_LANE_ORDER.map((lane) => makeLaneSection(lane, lane === "demographics" ? facts : [])),
      highlights: [], evidence_locators: [],
    })));
    render(<ProfileLaneList model={model} />);
    [0, 1, 2].forEach((index) => expect(screen.queryByText(`记录${index}`)).not.toBeInTheDocument());
    [3, 4, 5, 6, 7, 8].forEach((index) => expect(screen.getByText(`记录${index}`)).toBeInTheDocument());
    expect(model.items).toHaveLength(9);
    expect(model.itemById.get("fact-0")?.assertedObject).toBe("报告医师");
  });

  it("行政字段若参与要求、临床事件或来源待核仍可见", () => {
    const facts = [
      makeFactItem({ item_id: "linked", source_id: "source-linked", title: "规则关联签名", asserted_object: "报告医师", locator_ids: [] }),
      makeFactItem({ item_id: "referenced", source_id: "source-referenced", title: "事件引用签名", asserted_object: "审核医师", locator_ids: [], requirement_ids: [] }),
      makeFactItem({ item_id: "followup", source_id: "source-followup", title: "签名来源待核", asserted_object: "报告医师", locator_ids: [], requirement_ids: [], provenance_followup: true, provenance_reason: "需要核对原件" }),
    ];
    const event = makeEventItem({ locator_ids: [], requirement_ids: [], fact_ids: ["source-referenced"] });
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision({
      lanes: PROFILE_LANE_ORDER.map((lane) => makeLaneSection(lane,
        lane === "demographics" ? facts : lane === "symptoms_signs" ? [event] : [])),
      highlights: [], evidence_locators: [],
    })));
    render(<ProfileLaneList model={model} />);
    ["规则关联签名", "事件引用签名", "签名来源待核", "发热"].forEach((title) => expect(screen.getByText(title)).toBeInTheDocument());
  });

  it("医师字段带临床批注时保留，不把CS/NCS判断当作普通署名隐藏", () => {
    const values = ["NCS", "cs", "无临床意义，已签字", "已作研究者评估"];
    const facts = values.map((value, index) => makeFactItem({
      item_id: `annotation-${index}`, source_id: `annotation-source-${index}`,
      title: `临床批注${index}`, asserted_object: "报告医师", value,
      locator_ids: [], requirement_ids: [],
    }));
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision({
      lanes: PROFILE_LANE_ORDER.map((lane) => makeLaneSection(lane, lane === "demographics" ? facts : [])),
      highlights: [], evidence_locators: [],
    })));
    render(<ProfileLaneList model={model} />);
    values.forEach((_, index) => expect(screen.getByText(`临床批注${index}`)).toBeInTheDocument());
  });

  it("13 条泳道按稳定顺序全部展示（含空泳道）", () => {
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
    render(<ProfileLaneList model={model} />);
    // 每个泳道 section 带 aria-label，可独立定位
    const sections = screen.getAllByRole("region");
    expect(sections).toHaveLength(13);
    PROFILE_LANE_ORDER.forEach((lane, index) => {
      expect(sections[index]).toHaveAccessibleName(laneLabelFor(lane));
    });
  });

  it("空泳道保留说明，不判为资料缺口", () => {
    const model = adaptPatientProfile(
      decodePatientProfileRevision(
        makeRevision({
          lanes: PROFILE_LANE_ORDER.map((lane) => makeLaneSection(lane, [])),
          highlights: [],
          evidence_locators: [],
        }),
      ),
    );
    render(<ProfileLaneList model={model} />);
    expect(
      screen.getByText(/分区暂无记录不代表正常或否认/),
    ).toBeInTheDocument();
    expect(screen.getAllByText("暂无已整理记录")).toHaveLength(13);
    expect(screen.queryByText(/按资料缺口处理/)).not.toBeInTheDocument();
  });

  it("有条目泳道渲染条目卡片", () => {
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
    render(<ProfileLaneList model={model} />);
    expect(screen.getByText("基线血压 120/80 mmHg")).toBeInTheDocument();
    // 条目卡片位于人口学泳道内
    const demographics = screen.getByRole("region", { name: "人口学/基线" });
    expect(within(demographics).getByText("基线血压 120/80 mmHg")).toBeInTheDocument();
  });

  it("条目根节点提供稳定的 profile-item 锚点", () => {
    const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
    render(<ProfileLaneList model={model} />);
    expect(document.getElementById("profile-item-item-fact-1")).toBeInTheDocument();
  });
});
