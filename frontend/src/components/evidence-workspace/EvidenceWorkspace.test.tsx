// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { EvidenceWorkspace } from "./EvidenceWorkspace";

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function openWorkspace() {
  const view = render(<EvidenceWorkspace leftTitle="文件" leftContent="文件清单"
    centerTitle="文字" centerContent="原文" rightTitle="原件" rightContent="页图" />);
  const workspace = view.container.querySelector<HTMLElement>(".evidence-workspace")!;
  const widths = () => Array.from(workspace.style.gridTemplateColumns.matchAll(/([\d.]+)fr/g),
    (match) => Number(match[1]));
  return { ...view, workspace, widths };
}

it("原件默认占最大宽度，键盘只调整相邻栏并保留完整比例", () => {
  const { widths } = openWorkspace();
  expect(widths()).toEqual([20, 32, 48]);
  fireEvent.keyDown(screen.getByRole("separator", { name: "调整左栏宽度" }), { key: "ArrowRight" });
  expect(widths()).toEqual([22, 30, 48]);
  fireEvent.keyDown(screen.getByRole("separator", { name: "调整中栏宽度" }), { key: "ArrowLeft" });
  expect(widths()).toEqual([22, 28, 50]);
});

it.each(["调整左栏宽度", "调整中栏宽度"])("%s的极端拖动仍保留三栏及非相邻宽度", (label) => {
  vi.stubGlobal("PointerEvent", MouseEvent);
  const { workspace, widths } = openWorkspace();
  vi.spyOn(workspace, "getBoundingClientRect").mockReturnValue({ width: 1000 } as DOMRect);
  const separator = screen.getByRole("separator", { name: label });
  fireEvent.pointerDown(separator, { clientX: 0 });
  fireEvent.pointerMove(window, { clientX: 3000 });
  fireEvent.pointerUp(window);
  expect(widths()).toEqual(label === "调整左栏宽度" ? [28, 24, 48] : [20, 56, 24]);
  fireEvent.pointerDown(separator, { clientX: 0 });
  fireEvent.pointerMove(window, { clientX: -3000 });
  fireEvent.pointerUp(window);
  expect(widths()).toEqual(label === "调整左栏宽度" ? [16, 36, 48] : [20, 24, 56]);
  expect(widths().reduce((sum, value) => sum + value, 0)).toBe(100);
});
