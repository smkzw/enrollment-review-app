// @vitest-environment jsdom
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { EvidenceReader } from "./EvidenceReader";

describe("按需原件侧栏", () => {
  it("关闭后返回触发位置，恢复原滚动设置，不销毁查看状态", async () => {
    const user = userEvent.setup();
    const trigger = document.createElement("button");
    document.body.append(trigger); trigger.focus();
    document.body.style.overflow = "clip";
    const close = vi.fn();
    const view = render(<EvidenceReader title="检验原件" onClose={close}><input aria-label="页码" defaultValue="1" /></EvidenceReader>);
    expect(screen.getByRole("dialog", { name: "检验原件" })).toHaveAttribute("open");
    expect(document.body.style.overflow).toBe("hidden");
    await user.clear(screen.getByLabelText("页码")); await user.type(screen.getByLabelText("页码"), "8");
    await user.click(screen.getByRole("button", { name: "关闭原件" }));
    expect(close).toHaveBeenCalledOnce();
    view.rerender(<EvidenceReader title="检验原件" open={false} onClose={close}><input aria-label="页码" defaultValue="1" /></EvidenceReader>);
    expect(trigger).toHaveFocus(); expect(document.body.style.overflow).toBe("clip");
    view.rerender(<EvidenceReader title="检验原件" onClose={close}><input aria-label="页码" defaultValue="1" /></EvidenceReader>);
    expect(screen.getByLabelText("页码")).toHaveValue("8");
    view.unmount(); trigger.remove(); document.body.style.overflow = "";
  });
  it("原生Esc取消请求进入页面关闭动作，不靠重新加载退出", () => {
    const close = vi.fn();
    render(<EvidenceReader title="病历原件" onClose={close}><p>原件内容</p></EvidenceReader>);
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
    expect(close).toHaveBeenCalledOnce();
  });
});
