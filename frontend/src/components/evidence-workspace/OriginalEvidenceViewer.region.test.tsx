// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { OriginalEvidenceViewer } from "./OriginalEvidenceViewer";
import { getLocalVisualTask, startLocalVisualTask } from "../../api/evidence/localVisualHttp";
import type { ProcessingRevisionPageView } from "../../api/evidence";

vi.mock("../../api/evidence/localVisualHttp", () => ({ getLocalVisualTask: vi.fn(), startLocalVisualTask: vi.fn(), actOnLocalVisualTask: vi.fn() }));
const page: ProcessingRevisionPageView = { entryId: "entry", position: 1, sourceDocumentVersionId: "doc", pageNumber: 1,
  originalFrame: null, pageArtifactId: "page", ocrPageId: "ocr", status: "succeeded", statusLabel: "页面已就绪",
  failureReason: null, canOpen: true, imageAvailable: true, pageWidth: 400, pageHeight: 800 };
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getLocalVisualTask).mockResolvedValue({ found: false, jobId: null, state: null, text: null, region: null, configurationCurrent: true, canRetry: false });
  vi.mocked(startLocalVisualTask).mockResolvedValue("job");
  vi.stubGlobal("PointerEvent", MouseEvent);
  Object.defineProperties(HTMLElement.prototype, {
    setPointerCapture: { configurable: true, value: vi.fn() },
    hasPointerCapture: { configurable: true, value: () => true },
    releasePointerCapture: { configurable: true, value: vi.fn() },
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLElement.prototype, "setPointerCapture");
  Reflect.deleteProperty(HTMLElement.prototype, "hasPointerCapture");
  Reflect.deleteProperty(HTMLElement.prototype, "releasePointerCapture");
});

it("圈选按真实像素和显示旋转提交，跨页后不携带旧范围", async () => {
  const props = { revisionId: "rev", pages: [page], documentNames: new Map<string, string>(), selectedEntryId: "entry",
    selectedLocatorId: null, selectedPageLocators: [], onSelectPage: vi.fn(), allowLocalVerification: true };
  const { container, rerender } = render(<OriginalEvidenceViewer {...props} />);
  const image = screen.getByAltText("第 1 页原始资料");
  Object.defineProperties(image, { naturalWidth: { value: 1200 }, naturalHeight: { value: 2400 } });
  fireEvent.load(image);
  fireEvent.click(screen.getByRole("button", { name: "本页向右旋转" }));
  fireEvent.click(screen.getByRole("button", { name: "圈选原件局部" }));
  const canvas = container.querySelector(".original-evidence-page__canvas")!;
  vi.spyOn(canvas, "getBoundingClientRect").mockReturnValue({ left: 10, top: 20, width: 600, height: 300 } as DOMRect);
  fireEvent.pointerDown(canvas, { button: 0, clientX: 70, clientY: 50 });
  fireEvent.pointerMove(canvas, { clientX: 310, clientY: 170 });
  fireEvent.pointerUp(canvas);
  expect(screen.getByLabelText("待核实的圈选区域")).toHaveStyle({ left: "10%", top: "10%", width: "40%", height: "40%" });
  fireEvent.click(screen.getByRole("button", { name: "核实所选区域" }));
  await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", {
    x0: 240, y0: 120, x1: 1200, y1: 600, clockwise_degrees: 90,
  }));
  rerender(<OriginalEvidenceViewer {...props} pages={[{ ...page, entryId: "next", pageArtifactId: "next-page" }]} selectedEntryId="next" />);
  expect(screen.queryByLabelText("待核实的圈选区域")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "核实所选区域" })).not.toBeInTheDocument();
});
