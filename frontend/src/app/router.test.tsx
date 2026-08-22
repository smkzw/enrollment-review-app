// @vitest-environment jsdom
/**
 * hash 路由单元测试：默认首屏、导航、静默参数更新、前进/后退恢复。
 * 覆盖工作项验收“navigation”行为（spec: state-management §URL 状态）。
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";
import {
  buildHash,
  defaultPathForMode,
  navigate,
  parseHash,
  RouteLink,
  updateParams,
  useHashRoute,
} from "./router";
import { findRoute } from "./routes";

function RouteProbe() {
  const route = useHashRoute();
  return (
    <output data-testid="route">
      {route.path}?{route.params.toString()}
    </output>
  );
}

describe("hash router", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/");
    window.location.hash = "";
  });

  it("正式模式空地址直接进入已开放的方案工作台", () => {
    expect(defaultPathForMode(false)).toBe("/protocols");
    expect(defaultPathForMode(true)).toBe("/today");
  });

  it("正式模式可打开证据任务详情，不把真实深链落到占位页", () => {
    expect(findRoute("/tasks")?.component).not.toBeNull();
  });

  it("兼容不带井号的方案工作台直达地址", () => {
    window.history.replaceState(null, "", "/protocols?mode=first");
    const route = parseHash();
    expect(route.path).toBe("/protocols");
    expect(route.params.get("mode")).toBe("first");
  });

  it("空 hash 默认进入今日工作（无登录直达）", async () => {
    render(<RouteProbe />);
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent("/today?"),
    );
  });

  it("navigate 写入 hash 并更新路由", async () => {
    render(<RouteProbe />);
    navigate("/board", { stage: "screening" });
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "/board?stage=screening",
      ),
    );
    expect(window.location.hash).toBe("#/board?stage=screening");
  });

  it("updateParams 静默更新参数，不产生新历史记录", async () => {
    render(<RouteProbe />);
    navigate("/board", { stage: "screening" });
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "/board?stage=screening",
      ),
    );
    const historyLength = window.history.length;
    updateParams({ status: "clear_barrier" });
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "stage=screening&status=clear_barrier",
      ),
    );
    expect(window.history.length).toBe(historyLength);
  });

  it("updateParams 传 null 删除参数", async () => {
    render(<RouteProbe />);
    navigate("/board", { stage: "screening", status: "conflict" });
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "stage=screening&status=conflict",
      ),
    );
    updateParams({ status: null });
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "/board?stage=screening",
      ),
    );
    expect(window.location.hash).toBe("#/board?stage=screening");
  });

  it("后退/前进恢复之前的页面与参数", async () => {
    render(<RouteProbe />);
    navigate("/board", { stage: "screening" });
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "/board?stage=screening",
      ),
    );
    navigate("/today");
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent("/today?"),
    );
    window.history.back();
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent(
        "/board?stage=screening",
      ),
    );
    window.history.forward();
    await waitFor(() =>
      expect(screen.getByTestId("route")).toHaveTextContent("/today?"),
    );
  });

  it("RouteLink 生成规范 href（直达审核节点 URL 契约）", () => {
    render(
      <RouteLink
        to="/workbench"
        params={{ episode: "episode-uat-03-screening-gap_conflict" }}
      >
        打开审核
      </RouteLink>,
    );
    expect(screen.getByRole("link", { name: "打开审核" })).toHaveAttribute(
      "href",
      "#/workbench?episode=episode-uat-03-screening-gap_conflict",
    );
  });

  it("buildHash 忽略 null/undefined 参数", () => {
    expect(buildHash("/board", { stage: "screening", status: undefined })).toBe(
      "#/board?stage=screening",
    );
    expect(buildHash("/board")).toBe("#/board");
  });
});
