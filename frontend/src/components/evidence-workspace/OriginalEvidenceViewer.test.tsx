// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  LocatorView,
  ProcessingRevisionPageView,
} from "../../api/evidence";
import { OriginalEvidenceViewer } from "./OriginalEvidenceViewer";

const scrollIntoView = vi.fn();

beforeEach(() => {
  scrollIntoView.mockReset();
  Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
    configurable: true,
    value: scrollIntoView,
  });
});

afterEach(() => {
  Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
});

const readyPage: ProcessingRevisionPageView = {
  entryId: "entry-1",
  position: 1,
  sourceDocumentVersionId: "version-1",
  pageNumber: 1,
  originalFrame: null,
  pageArtifactId: "artifact-1",
  ocrPageId: "ocr-1",
  status: "succeeded",
  statusLabel: "页面已就绪",
  failureReason: null,
  canOpen: true,
  imageAvailable: true,
  pageWidth: 1000,
  pageHeight: 2000,
};

const failedPage: ProcessingRevisionPageView = {
  ...readyPage,
  entryId: "entry-2",
  position: 2,
  pageNumber: 2,
  pageArtifactId: "artifact-2",
  ocrPageId: null,
  status: "failed",
  statusLabel: "页面处理失败",
  failureReason: "原始页面读取失败。",
  canOpen: false,
  imageAvailable: false,
  pageWidth: null,
  pageHeight: null,
};

function locator(overrides: Partial<LocatorView> = {}): LocatorView {
  return {
    locatorId: "locator-1",
    pageArtifactId: "artifact-1",
    ocrPageId: "ocr-1",
    sourceDocumentVersionId: "version-1",
    pageNumber: 1,
    sourceLayer: "native_text",
    sourceLayerLabel: "原始资料文字层",
    sourceTextSha256: "a".repeat(64),
    targetId: "target-1",
    precision: "bbox",
    precisionLabel: "原文区域",
    degradationReason: null,
    textStart: 2,
    textEnd: 4,
    excerpt: "否认",
    disambiguation: "unique_match",
    locatorAlgorithmVersion: "locator-1",
    authenticity: "authenticated",
    matchConfidence: 1,
    bbox: { x0: 100, y0: 400, x1: 500, y1: 600 },
    coordinateFrame: {
      space: "page_image_pixels",
      pageWidth: 1000,
      pageHeight: 2000,
      rotation: 0,
      transformVersion: "transform-1",
    },
    coordinateTransformVersion: "transform-1",
    ...overrides,
  };
}

describe("OriginalEvidenceViewer", () => {
  it("只把已核验区域按页图比例映射为重点框", () => {
    render(
      <OriginalEvidenceViewer
        revisionId="revision-1"
        pages={[readyPage]}
        documentNames={new Map([["version-1", "筛选病历.pdf"]])}
        selectedEntryId="entry-1"
        selectedLocatorId="locator-1"
        selectedPageLocators={[
          locator(),
          locator({
            locatorId: "locator-degraded",
            precision: "page_excerpt",
            precisionLabel: "页内摘录",
            authenticity: "degraded",
            degradationReason: "未取得可信坐标。",
            bbox: null,
            coordinateFrame: null,
            coordinateTransformVersion: null,
          }),
        ]}
        onSelectPage={vi.fn()}
      />,
    );

    const box = screen.getByLabelText("重点标注：否认");
    expect(box).toHaveStyle({
      left: "10%",
      top: "20%",
      width: "40%",
      height: "10%",
    });
    expect(screen.getAllByLabelText(/^重点标注/)).toHaveLength(1);
    const image = screen.getByAltText("第 1 页原始资料");
    expect(image).toHaveAttribute(
      "src",
      "/api/v2/evidence-processing-revisions/revision-1/pages/entry-1/image",
    );
    expect(image).toHaveAttribute("loading", "eager");
  });

  it("对连续原件中的每个可用页面都立即加载原图", () => {
    render(
      <OriginalEvidenceViewer
        revisionId="revision-1"
        pages={[
          readyPage,
          {
            ...readyPage,
            entryId: "entry-ready-2",
            position: 2,
            pageNumber: 2,
            pageArtifactId: "artifact-ready-2",
            ocrPageId: "ocr-ready-2",
          },
        ]}
        documentNames={new Map([["version-1", "筛选病历.pdf"]])}
        selectedEntryId="entry-1"
        selectedLocatorId={null}
        selectedPageLocators={[]}
        onSelectPage={vi.fn()}
      />,
    );

    expect(screen.getAllByRole("img")).toHaveLength(2);
    for (const image of screen.getAllByRole("img")) {
      expect(image).toHaveAttribute("loading", "eager");
    }
  });

  it("只显示当前选中的真实区域，避免多个框遮挡原文", () => {
    render(
      <OriginalEvidenceViewer
        revisionId="revision-1"
        pages={[readyPage]}
        documentNames={new Map([["version-1", "筛选病历.pdf"]])}
        selectedEntryId="entry-1"
        selectedLocatorId="locator-1"
        selectedPageLocators={[
          locator(),
          locator({
            locatorId: "locator-2",
            excerpt: null,
            precisionLabel: "经核验的原文区域",
            bbox: { x0: 550, y0: 700, x1: 850, y1: 900 },
          }),
        ]}
        onSelectPage={vi.fn()}
      />,
    );

    const selected = screen.getByLabelText("重点标注：否认");

    expect(selected).toHaveClass("original-evidence-page__box--selected");
    expect(selected).toHaveAttribute("title", "重点标注：否认");
    expect(screen.getAllByLabelText(/^重点标注/)).toHaveLength(1);
  });

  it("未选择具体定位时保持原件无遮挡", () => {
    render(
      <OriginalEvidenceViewer
        revisionId="revision-1"
        pages={[readyPage]}
        documentNames={new Map([["version-1", "筛选病历.pdf"]])}
        selectedEntryId="entry-1"
        selectedLocatorId={null}
        selectedPageLocators={[locator()]}
        onSelectPage={vi.fn()}
      />,
    );

    expect(screen.queryByLabelText(/^重点标注/)).not.toBeInTheDocument();
  });

  it("选中定位变化时居中平滑滚动，用户主动滚动时不回拉", () => {
    const locators = [
      locator(),
      locator({
        locatorId: "locator-2",
        excerpt: "无发热",
        bbox: { x0: 550, y0: 700, x1: 850, y1: 900 },
      }),
    ];
    const props = {
      revisionId: "revision-1",
      pages: [readyPage],
      documentNames: new Map([["version-1", "筛选病历.pdf"]]),
      selectedEntryId: "entry-1",
      selectedPageLocators: locators,
      onSelectPage: vi.fn(),
    };
    const { rerender } = render(
      <OriginalEvidenceViewer {...props} selectedLocatorId={null} />,
    );

    rerender(
      <OriginalEvidenceViewer {...props} selectedLocatorId="locator-1" />,
    );
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
    expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "center",
      inline: "nearest",
    });

    const viewer = screen.getByLabelText("原始资料查看区");
    fireEvent.wheel(viewer);
    fireEvent.scroll(viewer);
    rerender(
      <OriginalEvidenceViewer {...props} selectedLocatorId="locator-2" />,
    );
    expect(scrollIntoView).toHaveBeenCalledTimes(1);
  });

  it("失败页保留连续页位并可联动选择，但不请求伪造原图", () => {
    const onSelectPage = vi.fn();
    render(
      <OriginalEvidenceViewer
        revisionId="revision-1"
        pages={[readyPage, failedPage]}
        documentNames={new Map([["version-1", "筛选病历.pdf"]])}
        selectedEntryId="entry-1"
        selectedLocatorId={null}
        selectedPageLocators={[]}
        onSelectPage={onSelectPage}
      />,
    );

    expect(screen.getByText("原始页面读取失败。")).toBeInTheDocument();
    expect(screen.queryByAltText("第 2 页原始资料")).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "筛选病历.pdf 第 2 页" }),
    );
    expect(onSelectPage).toHaveBeenCalledWith("entry-2");
  });
});
