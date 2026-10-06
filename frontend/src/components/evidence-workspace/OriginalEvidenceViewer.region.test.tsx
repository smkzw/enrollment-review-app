// @vitest-environment jsdom
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { OriginalEvidenceViewer } from "./OriginalEvidenceViewer";
import { getLocalVisualTask, startLocalVisualTask } from "../../api/evidence/localVisualHttp";
import type { ProcessingRevisionPageView } from "../../api/evidence";

vi.mock("../../api/evidence/localVisualHttp", async (original) => ({
  ...await original<typeof import("../../api/evidence/localVisualHttp")>(),
  getLocalVisualTask: vi.fn(), startLocalVisualTask: vi.fn(), actOnLocalVisualTask: vi.fn(),
}));
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
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLElement.prototype, "setPointerCapture");
  Reflect.deleteProperty(HTMLElement.prototype, "hasPointerCapture");
  Reflect.deleteProperty(HTMLElement.prototype, "releasePointerCapture");
});

it("查看器转交本页摘录，不把定位按钮当作文字保存或核实授权", async () => {
  const excerpt = "报告时间：2026-02-03 10:12";
  vi.mocked(getLocalVisualTask).mockResolvedValue({ found: true, jobId: "read-job", state: "completed",
    text: "读取结果", region: { x0: 20, y0: 20, x1: 80, y1: 80, clockwise_degrees: 0 },
    readingRegion: { x0: 20, y0: 20, x1: 80, y1: 80, clockwise_degrees: 0 },
    configurationCurrent: true, canRetry: false, structuredRead: { items: [{
      label: "报告时间", raw_value: "2026-02-03 10:12", raw_unit: null, reference_text: null,
      time_label: "报告时间", annotation_target: null, excerpt, position: "页底", script: "printed",
      legibility: "clear", proposed_bbox: { x0: 0, y0: 0, x1: 1000, y1: 1000 },
    }], unresolved: [] } });
  const prepare = vi.fn();
  render(<OriginalEvidenceViewer revisionId="rev" pages={[page]} documentNames={new Map()}
    selectedEntryId="entry" selectedLocatorId={null} selectedPageLocators={[]}
    onSelectPage={vi.fn()} allowLocalVerification onPrepareCorrection={prepare} />);
  fireEvent.click(await screen.findByText("查看本次读取结果（尚未采用）"));
  fireEvent.click(screen.getByRole("button", { name: "将第1项报告时间转到文字校对" }));
  expect(prepare).toHaveBeenCalledWith({ revisionId: "rev", pageId: "page", jobId: "read-job", itemIndex: 0, excerpt });
  expect(startLocalVisualTask).not.toHaveBeenCalled();
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
  expect(container.querySelector(".evidence-pages-scroll")!.scrollTop).toBe(0);
  expect(screen.getByLabelText("待核实的圈选区域")).toHaveStyle({ left: "10%", top: "10%", width: "40%", height: "40%" });
  fireEvent.click(screen.getByRole("button", { name: "核实所选区域" }));
  await waitFor(() => expect(startLocalVisualTask).toHaveBeenCalledWith("rev", "page", {
    x0: 240, y0: 120, x1: 1200, y1: 600, clockwise_degrees: 90,
  }));
  rerender(<OriginalEvidenceViewer {...props} pages={[{ ...page, entryId: "next", pageArtifactId: "next-page" }]} selectedEntryId="next" />);
  expect(screen.queryByLabelText("待核实的圈选区域")).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "核实所选区域" })).not.toBeInTheDocument();
});

it("显式定位读取区域才滚动到原件，保留旋转且不再次读取", async () => {
  vi.mocked(getLocalVisualTask).mockResolvedValue({ found: true, jobId: "completed", state: "completed", text: "有待核实的原文",
    region: { x0: 240, y0: 720, x1: 480, y1: 780, clockwise_degrees: 270 }, configurationCurrent: true, canRetry: false });
  const onSelectPage = vi.fn();
  const onReadingRotationChange = vi.fn();
  const { container } = render(<OriginalEvidenceViewer revisionId="rev" pages={[page]} documentNames={new Map()}
    selectedEntryId="entry" selectedLocatorId={null} selectedPageLocators={[]} onSelectPage={onSelectPage}
    onReadingRotationChange={onReadingRotationChange} allowLocalVerification />);
  const image = screen.getByAltText("第 1 页原始资料");
  Object.defineProperties(image, { naturalWidth: { value: 1200 }, naturalHeight: { value: 2400 } });
  fireEvent.load(image);
  const scroll = container.querySelector<HTMLElement>(".evidence-pages-scroll")!;
  Object.defineProperty(scroll, "clientHeight", { configurable: true, value: 300 });
  vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockImplementation(function (this: HTMLElement) {
    if (this.classList.contains("original-evidence-page__region")) return { top: 700, left: 80, width: 40, height: 20 } as DOMRect;
    return { top: 100, left: 0, width: 400, height: 300 } as DOMRect;
  });
  fireEvent.click(await screen.findByRole("button", { name: "定位本次核实区域" }));
  expect(scroll.scrollTop).toBe(460);
  expect(screen.getByLabelText("待核实的圈选区域")).toHaveStyle({ left: "10%", top: "60%", width: "10%", height: "5%" });
  expect(onReadingRotationChange).toHaveBeenCalledWith("page", 270);
  expect(onSelectPage).not.toHaveBeenCalled();
  expect(startLocalVisualTask).not.toHaveBeenCalled();
});
