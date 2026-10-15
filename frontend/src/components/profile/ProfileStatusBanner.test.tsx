// @vitest-environment jsdom
/**
 * ProfileStatusBanner：生成中/失败/陈旧三种状态提示；正常已生成不渲染。
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  adaptPatientProfile,
} from "../../features/patient-profile/model";
import {
  decodePatientProfileRevision,
} from "../../api/patient-profile/patientProfileViewModels";
import { makeRevision } from "../../api/patient-profile/patientProfileFixtures";
import { ProfileStatusBanner } from "./ProfileStatusBanner";

function modelFor(overrides: Parameters<typeof makeRevision>[0]) {
  return adaptPatientProfile(decodePatientProfileRevision(makeRevision(overrides)));
}

describe("ProfileStatusBanner", () => {
  it("正常已生成（succeeded 且有条目）不渲染任何提示", () => {
    const { container } = render(
      <ProfileStatusBanner model={modelFor({ status: "succeeded", status_label: "已生成" })} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("生成中：role=status 提示生成中", () => {
    render(
      <ProfileStatusBanner model={modelFor({ status: "generating", status_label: "生成中" })} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("生成中");
    expect(screen.getByText(/正在整理已核实的病史、用药和检查记录/)).toBeInTheDocument();
  });

  it("失败：role=alert 提示生成失败，不提示已生成", () => {
    render(
      <ProfileStatusBanner model={modelFor({ status: "failed", status_label: "生成失败" })} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("生成失败");
    expect(screen.getByRole("alert")).toHaveTextContent("不表示病史、用药或检查记录为空");
    expect(screen.queryByText(/已生成/)).not.toBeInTheDocument();
  });

  it("陈旧：提示资料已更新、档案待重新生成", () => {
    render(
      <ProfileStatusBanner model={modelFor({ status: "stale", status_label: "资料已更新，档案待重新生成" })} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("资料已更新，档案待重新生成");
    expect(screen.getByText(/上一版已生成档案的内容/)).toBeInTheDocument();
  });
});
