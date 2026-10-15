// @vitest-environment jsdom
/**
 * ProfileHighlights：首屏只展示后端 highlights（结构化原因），无 highlight 时给中性空提示。
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  adaptPatientProfile,
} from "../../features/patient-profile/model";
import {
  decodePatientProfileRevision,
} from "../../api/patient-profile/patientProfileViewModels";
import {
  makeHighlight,
  makeExpectationItem,
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

  it("大量待核条目先收束展示，展开后全量可达", () => {
    const revision = makeRevision();
    const expectations = Array.from({ length: 9 }, (_, index) => makeExpectationItem({
      item_id: `expectation-${index}`,
      source_id: `expectation-source-${index}`,
      title: `待核项目 ${index + 1}`,
    }));
    revision.lanes = revision.lanes.map((lane) =>
      lane.lane === "test_exam_score" ? { ...lane, items: expectations } : lane,
    );
    revision.highlights = expectations.map((item) => makeHighlight({
      item_id: item.item_id,
      reasons: ["current_due_expectation_gap"],
      reason_labels: ["当前到期资料缺口"],
      gap_type: "referenced_file_missing",
      gap_type_label: "已引用文件未提供",
    }));
    revision.pending_review_count = expectations.length;
    const model = adaptPatientProfile(decodePatientProfileRevision(revision));

    render(<ProfileHighlights model={model} />);
    expect(screen.getByText("待核项目 1")).toBeInTheDocument();
    expect(screen.queryByText("待核项目 9")).not.toBeInTheDocument();
    const expand = screen.getByRole("button", { name: "展开其余 1 项" });
    expect(expand).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(expand);
    expect(screen.getByText("待核项目 9")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "收起重点明细" }));
    expect(screen.queryByText("待核项目 9")).not.toBeInTheDocument();
  });

  it("首屏不因资料缺口数量多而遮住研究者判断项", () => {
    const revision = makeRevision();
    const expectations = Array.from({ length: 10 }, (_, index) => makeExpectationItem({
      item_id: `expectation-${index}`,
      source_id: `expectation-source-${index}`,
      title: index === 9 ? "待研究者判断的检查" : `待补资料 ${index + 1}`,
      gap_type: index === 9 ? "professional_judgment" : "record_incomplete",
      gap_type_label: index === 9 ? "待研究者判断" : "本次资料未见相关记录",
    }));
    revision.lanes = revision.lanes.map((lane) =>
      lane.lane === "test_exam_score" ? { ...lane, items: expectations } : lane,
    );
    revision.highlights = expectations.map((item) => makeHighlight({
      item_id: item.item_id,
      reasons: ["current_due_expectation_gap"],
      reason_labels: ["当前到期资料缺口"],
      gap_type: item.gap_type,
      gap_type_label: item.gap_type_label,
    }));
    revision.pending_review_count = expectations.length;
    render(<ProfileHighlights model={adaptPatientProfile(decodePatientProfileRevision(revision))} />);
    expect(screen.getByText("待研究者判断的检查")).toBeInTheDocument();
    expect(screen.queryByText("待补资料 9")).not.toBeInTheDocument();
  });
});
