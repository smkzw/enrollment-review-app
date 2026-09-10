// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type {
  ProfileGapTypeWire,
  ProfileLaneWire,
  ProfileItemWire,
} from "../../api/patient-profile";
import { decodePatientProfileRevision } from "../../api/patient-profile/patientProfileViewModels";
import {
  makeConflictItem,
  makeExpectationItem,
  makeLaneSection,
  makeRevision,
  laneLabelFor,
  PROFILE_LANE_ORDER,
} from "../../api/patient-profile/patientProfileFixtures";
import { adaptPatientProfile } from "../../features/patient-profile/model";
import {
  ProfileTodoSummaryCard,
  profileTodoItemIds,
  summarizeProfileTodos,
} from "./ProfileTodoSummaryCard";

function expectation(
  itemId: string,
  lane: ProfileLaneWire,
  gapType: ProfileGapTypeWire,
): ProfileItemWire {
  return makeExpectationItem({
    item_id: itemId,
    lane,
    lane_label: laneLabelFor(lane),
    gap_type: gapType,
    gap_type_label: gapType,
  });
}

function todoModel() {
  const items: ProfileItemWire[] = [
    expectation("missing-record", "demographics", "record_incomplete"),
    expectation("missing-file", "target_disease", "referenced_file_missing"),
    expectation("missing-procedure", "symptoms_signs", "required_procedure_not_done"),
    expectation("missing-history", "medical_history", "historical_source_unavailable"),
    expectation("judgment-professional", "medication", "professional_judgment"),
    expectation("judgment-observation", "non_drug_treatment", "observation_unverified"),
    expectation("manual-ocr", "test_exam_score", "ocr_or_parse_risk"),
    expectation("manual-fields", "allergy_infection_immune", "result_fields_missing"),
    expectation("manual-description", "reproductive", "description_insufficient"),
    expectation("manual-date", "social_environmental", "date_or_anchor_missing"),
    expectation("manual-provenance", "special_history", "provenance_followup"),
    makeConflictItem({
      item_id: "conflict-unresolved",
      lane: "evidence_quality",
      lane_label: laneLabelFor("evidence_quality"),
      conflict_resolution_revision: null,
    }),
    makeConflictItem({
      item_id: "conflict-interpretation",
      lane: "evidence_quality",
      lane_label: laneLabelFor("evidence_quality"),
      conflict_resolution_revision: 2,
      gap_type: "interpretation_conflict",
      gap_type_label: "解释材料与方案不一致",
    }),
  ];
  const revision = makeRevision({
    lanes: PROFILE_LANE_ORDER.map((lane) =>
      makeLaneSection(
        lane,
        items.filter((item) => item.lane === lane),
      ),
    ),
    highlights: [],
  });
  return adaptPatientProfile(decodePatientProfileRevision(revision));
}

function emptyModel() {
  return adaptPatientProfile(
    decodePatientProfileRevision(
      makeRevision({
        lanes: PROFILE_LANE_ORDER.map((lane) => makeLaneSection(lane, [])),
        highlights: [],
        evidence_locators: [],
      }),
    ),
  );
}

describe("ProfileTodoSummaryCard", () => {
  it("按 gapType 聚合四组，并按未解决冲突组而非成员数计数", () => {
    const model = todoModel();

    expect(summarizeProfileTodos(model)).toEqual({
      missing: 4,
      judgment: 2,
      conflict: 2,
      manual_review: 5,
    });
    expect(profileTodoItemIds(model, "conflict")).toEqual([
      "conflict-unresolved",
      "conflict-interpretation",
    ]);

    render(<ProfileTodoSummaryCard model={model} onNavigate={() => undefined} />);
    expect(screen.getByTestId("profile-todo-missing")).toHaveAccessibleName(
      "待补资料 4 项",
    );
    expect(screen.getByTestId("profile-todo-judgment")).toHaveAccessibleName(
      "待研究者判断 2 项",
    );
    expect(screen.getByTestId("profile-todo-conflict")).toHaveAccessibleName(
      "资料有矛盾 2 项",
    );
    expect(screen.getByTestId("profile-todo-manual_review")).toHaveAccessibleName(
      "待人工核对 5 项",
    );
  });

  it("四组均为零时显示事实性绿条", () => {
    render(
      <ProfileTodoSummaryCard model={emptyModel()} onNavigate={() => undefined} />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "本次提交资料中，暂无待补资料、待判断、矛盾或待核对事项",
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("点击非零组徽章回调对应的机器分组", async () => {
    const onNavigate = vi.fn();
    const user = userEvent.setup();
    render(<ProfileTodoSummaryCard model={todoModel()} onNavigate={onNavigate} />);

    await user.click(screen.getByRole("button", { name: "待人工核对 5 项" }));
    expect(onNavigate).toHaveBeenCalledTimes(1);
    expect(onNavigate).toHaveBeenCalledWith("manual_review");
  });
});
