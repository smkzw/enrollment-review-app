// @vitest-environment jsdom
/**
 * ProfileItemCard：事件时间与记录时间分开、来源强度/极性/值、用药信息、
 * 冲突并列成员与资料期望状态；定位只呈现真实定位数量与精度词。
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import {
  adaptPatientProfile,
} from "../../features/patient-profile/model";
import {
  decodePatientProfileRevision,
} from "../../api/patient-profile/patientProfileViewModels";
import {
  makeRevision,
} from "../../api/patient-profile/patientProfileFixtures";
import { ProfileItemCard } from "./ProfileItemCard";

function demographicsFact() {
  const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
  const lane = model.lanes.find((candidate) => candidate.lane === "demographics");
  const item = lane?.items[0];
  if (item === undefined) throw new Error("测试数据缺少人口学条目");
  return { model, item };
}

function medicationExposure() {
  const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
  const lane = model.lanes.find((candidate) => candidate.lane === "medication");
  const item = lane?.items[0];
  if (item === undefined) throw new Error("测试数据缺少用药暴露条目");
  return { model, item };
}

function conflictItem() {
  const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
  const lane = model.lanes.find((candidate) => candidate.lane === "evidence_quality");
  const item = lane?.items[0];
  if (item === undefined) throw new Error("测试数据缺少冲突条目");
  return { model, item };
}

function expectationItem() {
  const model = adaptPatientProfile(decodePatientProfileRevision(makeRevision()));
  const lane = model.lanes.find((candidate) => candidate.lane === "test_exam_score");
  const item = lane?.items[0];
  if (item === undefined) throw new Error("测试数据缺少资料期望条目");
  return { model, item };
}

describe("ProfileItemCard", () => {
  it("事件时间与记录时间分开展示，记录时间使用北京时间", () => {
    const { model, item } = demographicsFact();
    render(<ProfileItemCard model={model} item={item} />);
    const row = screen.getByText("事件时间").closest("div");
    expect(row).toHaveTextContent("2026-03（精度：月）");
    expect(row).toHaveTextContent("2026-03-01 至 2026-03-31");
    const recordRow = screen.getByText("记录时间").closest("div");
    expect(recordRow).toHaveTextContent("2026年8月22日 20:00（北京时间）");
  });

  it("日期占位符以临床用户可读方式展示且不改变精度", () => {
    const { model, item } = demographicsFact();
    const unknownDateItem = {
      ...item,
      startRange: {
        sourceText: "2020.UK.UK",
        precision: "year" as const,
        precisionLabel: "年",
        lowerBound: "2020-01-01",
        upperBound: "2020-12-31",
      },
    };
    render(<ProfileItemCard model={model} item={unknownDateItem} />);
    const row = screen.getByText("事件时间").closest("div");
    expect(row).toHaveTextContent("2020年月不详日不详（精度：年）");
    expect(row).not.toHaveTextContent("UK");
  });

  it("展示来源强度、记录性质、项目与结果（带单位）", () => {
    const { model, item } = demographicsFact();
    render(<ProfileItemCard model={model} item={item} />);
    expect(screen.getByText("来源：当前研究病历直接记录")).toBeInTheDocument();
    expect(screen.getByText("肯定")).toBeInTheDocument();
    expect(screen.getByText("血压")).toBeInTheDocument();
    expect(screen.getByText("120/80 mmHg")).toBeInTheDocument();
  });

  it("用药暴露展示药名、类别、适应证、剂量、频次与途径", () => {
    const { model, item } = medicationExposure();
    render(<ProfileItemCard model={model} item={item} />);
    const row = screen.getByText("用药信息").closest("div");
    expect(row).toHaveTextContent("阿司匹林");
    expect(row).toHaveTextContent("类别：抗血小板药");
    expect(row).toHaveTextContent("适应证：心血管预防");
    expect(row).toHaveTextContent("剂量：100 mg");
    expect(row).toHaveTextContent("频次：每日一次");
    expect(row).toHaveTextContent("途径：口服");
  });

  it("冲突条目并列展示成员数量与解决状态", () => {
    const { model, item } = conflictItem();
    render(<ProfileItemCard model={model} item={item} />);
    const row = screen.getByText("冲突并列").closest("div");
    expect(row).toHaveTextContent("相互矛盾的记录 2 条");
    expect(row).toHaveTextContent("已在档案第 2 版解决");
  });

  it("资料核对展示状态、缺口原因与说明", () => {
    const { model, item } = expectationItem();
    render(<ProfileItemCard model={model} item={item} />);
    const row = screen.getByText("已引用未提供").closest("div");
    expect(row).toHaveTextContent("资料核对");
    expect(row).toHaveTextContent("缺口：已引用文件未提供");
    expect(row).toHaveTextContent("筛选记录引用基线血常规报告");
  });

  it("真实定位只展示数量与精度词，不出现合成坐标", () => {
    const { model, item } = demographicsFact();
    render(<ProfileItemCard model={model} item={item} />);
    const row = screen.getByText("原文定位").closest("div");
    expect(row).toHaveTextContent("1 处");
    expect(row).toHaveTextContent("原文区域");
    expect(screen.queryByText(/x0|y0|x1|y1|100|200|400|320/)).not.toBeInTheDocument();
  });

  it("只为有定位的事实提供核对并修订入口，冲突条目不直接编辑", async () => {
    const { model, item } = demographicsFact();
    const onRequestCorrection = vi.fn();
    const user = userEvent.setup();
    render(
      <ProfileItemCard
        model={model}
        item={item}
        onRequestCorrection={onRequestCorrection}
      />,
    );
    await user.click(screen.getByRole("button", { name: `核对并修订“${item.title}”` }));
    expect(onRequestCorrection).toHaveBeenCalledWith(item);

    const conflict = conflictItem();
    const conflictRender = render(
      <ProfileItemCard
        model={conflict.model}
        item={conflict.item}
        onRequestCorrection={onRequestCorrection}
      />,
    );
    expect(within(conflictRender.container).queryByRole("button", { name: /核对并修订/ })).not.toBeInTheDocument();
  });

  it("不显示任何入排结论、行动数量或通过/不通过语言", () => {
    const { model, item } = demographicsFact();
    render(<ProfileItemCard model={model} item={item} />);
    expect(
      screen.queryByText(/入排结论|行动数量|负责方|通过|不通过/),
    ).not.toBeInTheDocument();
  });
});
