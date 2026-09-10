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
  makeRevision,
} from "../../api/patient-profile/patientProfileFixtures";
import { ProfileLaneList } from "./ProfileLaneList";

describe("ProfileLaneList", () => {
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
