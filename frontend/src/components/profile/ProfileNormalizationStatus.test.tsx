// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProfileNormalizationStatus } from "./ProfileNormalizationStatus";

describe("ProfileNormalizationStatus", () => {
  it("idle 不渲染", () => {
    const { container } = render(
      <ProfileNormalizationStatus state={{ status: "idle" }} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("失败文案含具体恢复动作且无技术词", () => {
    render(
      <ProfileNormalizationStatus
        state={{
          status: "error",
          message: "当前资料版本已更新。",
          recoveryHint: "请点击「重新整理个例档案」。",
          canRetry: true,
        }}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("个例档案整理未完成");
    expect(screen.getByRole("button", { name: "重新整理个例档案" })).toBeInTheDocument();
    expect(screen.queryByText(/Agent|pipeline|schema|provider/i)).not.toBeInTheDocument();
  });

  it("陈旧相位展示重新整理", () => {
    render(
      <ProfileNormalizationStatus
        state={{
          status: "active",
          jobId: "job-1",
          phase: "stale",
          title: "资料已更新，需重新整理个例档案",
          recoveryHint: "请点击「重新整理个例档案」按当前已启用资料生成新档案；上一版内容仍可查阅。",
          job: null,
          canRetry: true,
        }}
        onRetry={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("个例档案整理状态")).toHaveTextContent(
      "资料已更新，需重新整理个例档案",
    );
    expect(screen.getByRole("button", { name: "重新整理个例档案" })).toBeInTheDocument();
  });
});
