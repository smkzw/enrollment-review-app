// @vitest-environment jsdom
/**
 * ProfileHighlights：首屏只展示后端 highlights（结构化原因），无 highlight 时给中性空提示。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  adaptPatientProfile,
} from "../../features/patient-profile/model";
import {
  decodePatientProfileRevision,
} from "../../api/patient-profile/patientProfileViewModels";
import {
  makeHighlight,
  makeRevision,
} from "../../api/patient-profile/patientProfileFixtures";
import { ProfileHighlights } from "./ProfileHighlights";

describe("ProfileHighlights", () => {
  it("空 highlight 给中性空提示，不发明重点", () => {
    const model = adaptPatientProfile(
      decodePatientProfileRevision(makeRevision({ highlights: [] })),
    );
    render(<ProfileHighlights model={model} />);
    expect(screen.getByText("当前没有需要重点提示的条目。")).toBeInTheDocument();
  });

  it("逐条展示后端 highlight 原因、资料缺口与说明", () => {
    const model = adaptPatientProfile(
      decodePatientProfileRevision(
        makeRevision({
          highlights: [
            makeHighlight({
              item_id: "item-fact-1",
              reasons: ["source_report_abnormal"],
              reason_labels: ["原报告异常"],
              gap_type: "record_incomplete",
              gap_type_label: "记录不完整",
              detail: "基线血压报告的记录时间与检验单不一致。",
            }),
          ],
        }),
      ),
    );
    render(<ProfileHighlights model={model} />);
    expect(screen.getByText("原报告异常")).toBeInTheDocument();
    expect(screen.getByText(/资料缺口：记录不完整/)).toBeInTheDocument();
    expect(
      screen.getByText("基线血压报告的记录时间与检验单不一致。"),
    ).toBeInTheDocument();
    // 突出条目的标题来自档案条目（未在前端合成）
    expect(screen.getByText("基线血压 120/80 mmHg")).toBeInTheDocument();
  });

  it("不显示任何入排结论或行动语言", () => {
    const model = adaptPatientProfile(
      decodePatientProfileRevision(makeRevision()),
    );
    render(<ProfileHighlights model={model} />);
    expect(screen.queryByText(/入排结论|行动数量|负责方|通过|不通过/)).not.toBeInTheDocument();
  });
});
