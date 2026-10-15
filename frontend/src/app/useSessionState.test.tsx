// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { useSessionState } from "./useSessionState";

function BooleanTrial() {
  const [value, setValue] = useSessionState(
    "trial:boolean",
    false,
    (candidate) => (typeof candidate === "boolean" ? candidate : null),
  );
  return (
    <button type="button" onClick={() => setValue((current) => !current)}>
      {value ? "已保存" : "未保存"}
    </button>
  );
}

describe("会话内试用状态", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("接受通过校验的状态并保存后续操作", async () => {
    window.sessionStorage.setItem("trial:boolean", "true");
    const user = userEvent.setup();
    render(<BooleanTrial />);
    expect(screen.getByRole("button", { name: "已保存" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "已保存" }));
    expect(window.sessionStorage.getItem("trial:boolean")).toBe("false");
  });

  it("拒绝损坏或旧格式数据并回到初始状态", () => {
    window.sessionStorage.setItem("trial:boolean", JSON.stringify({ saved: true }));
    render(<BooleanTrial />);
    expect(screen.getByRole("button", { name: "未保存" })).toBeInTheDocument();
  });
});
