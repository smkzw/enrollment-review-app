// @vitest-environment jsdom
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { LocatorView } from "../../api/evidence";
import { FrozenReviewEvidence } from "./FrozenReviewEvidence";

const mocks = vi.hoisted(() => ({ revision: vi.fn(), snapshot: vi.fn(), viewer: vi.fn() }));
vi.mock("../../api/evidence", () => ({ getEvidenceRepository: () => ({
  getProcessingRevision: mocks.revision, getEvidenceSnapshot: mocks.snapshot,
}) }));
vi.mock("../evidence-workspace/OriginalEvidenceViewer", () => ({ OriginalEvidenceViewer: (props: unknown) => {
  mocks.viewer(props); return <div>原件查看区</div>;
} }));
const context = { projectId: "project", subjectId: "subject", reviewEpisodeId: "episode",
  completeProcessingRevisionId: "complete", evidenceSnapshotV2Id: "snapshot" };
const locator: LocatorView = { locatorId: "source-1", pageArtifactId: "page", ocrPageId: null,
  sourceDocumentVersionId: "document", pageNumber: 1, sourceLayer: "effective_text", sourceLayerLabel: "原文",
  sourceTextSha256: "a".repeat(64), targetId: "target", precision: "text_range", precisionLabel: "识别文字",
  degradationReason: null, textStart: 0, textEnd: 6, excerpt: "年龄：52岁", disambiguation: "unique_match",
  locatorAlgorithmVersion: "locator", authenticity: "authenticated", matchConfidence: null,
  bbox: null, coordinateFrame: null, coordinateTransformVersion: null };
const shared = { projectId: context.projectId, subjectId: context.subjectId, reviewEpisodeId: context.reviewEpisodeId,
  evidenceSnapshotId: "snapshot" };
beforeEach(() => {
  mocks.viewer.mockReset();
  mocks.revision.mockReset().mockResolvedValue({ ...shared, revisionId: "complete", pages: [{
    entryId: "entry", pageArtifactId: "page", sourceDocumentVersionId: "document", pageNumber: 1,
  }] });
  mocks.snapshot.mockReset().mockResolvedValue({ ...shared, members: [{
    sourceDocumentVersionId: "document", fileName: "检验报告.pdf",
  }] });
});

describe("历史报告原件查看", () => {
  it("页级定位只说明一次，全部不同摘录仍可选择且原数据不变", async () => {
    const user = userEvent.setup();
    const rows = [locator, { ...locator, locatorId: "source-2", excerpt: "检查结果已记录" }];
    const before = JSON.stringify(rows);
    render(<FrozenReviewEvidence context={context} locators={rows} title="年龄依据" onClose={vi.fn()} />);
    const navigation = await screen.findByRole("navigation", { name: "本条审核的原文摘录" });
    expect(within(navigation).getAllByRole("button")).toHaveLength(2);
    expect(screen.getAllByText("仅定位到所在页面，未标注具体区域")).toHaveLength(1);
    await user.click(within(navigation).getByRole("button", { name: /检查结果已记录/ }));
    expect(mocks.viewer).toHaveBeenLastCalledWith(expect.objectContaining({ selectedLocatorId: "source-2",
      selectedEntryId: "entry", revisionId: "complete", selectedPageLocators: [rows[1]] }));
    expect(screen.getAllByText("仅定位到所在页面，未标注具体区域")).toHaveLength(1);
    expect(JSON.stringify(rows)).toBe(before);
  });

  it.each(["mentioned", "unresolved", "not_seen"] as const)("保留%s来源性质，不把范围或待核文本说成已采用", async disposition => {
    const user = userEvent.setup();
    render(<FrozenReviewEvidence context={context} locators={[locator]} title="冻结原件" onClose={vi.fn()}
      pageRefs={[{ sourceDocumentVersionId: "document", pageArtifactId: "page", pageNumber: 1,
        excerpt: "本次核对内容", disposition }]} />);
    const navigation = await screen.findByRole("navigation", { name: "本条审核的原文摘录" });
    await user.click(within(navigation).getByRole("button", { name: /本次核对内容/ }));
    const label = { mentioned: "原文摘录", unresolved: "待核原文", not_seen: "核对范围" }[disposition];
    expect(within(navigation).getByText(label)).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent(disposition === "not_seen"
      ? "本页未见相关记录，不代表明确否认" : disposition === "unresolved"
      ? "原文尚待核清，仅定位页面" : "原文摘录，仅定位页面");
    expect(navigation).not.toHaveTextContent("已采用");
    expect(mocks.viewer).toHaveBeenLastCalledWith(expect.objectContaining({ selectedLocatorId: null, selectedPageLocators: [] }));
  });

  it.each(["authenticated", "degraded", "rejected"] as const)("区域标注说明不越过%s定位状态", async authenticity => {
    render(<FrozenReviewEvidence context={context} locators={[{ ...locator, precision: "bbox", authenticity,
      bbox: { x0: 10, x1: 50, y0: 10, y1: 20 }, coordinateFrame: {
        space: "rendered_page_pixels", pageWidth: 1000, pageHeight: 2000, rotation: 0, transformVersion: "identity" } }]}
      title="定位状态" onClose={vi.fn()} />);
    await screen.findByRole("navigation");
    expect(screen.getByRole("status")).toHaveTextContent(authenticity === "authenticated"
      ? "已标出原文位置" : "仅定位到所在页面，未标注具体区域");
  });

  it.each(["bbox", "coordinateFrame"] as const)("缺少%s时不声称已经标出区域", async field => {
    const row: LocatorView = { ...locator, precision: "bbox", bbox: { x0: 10, x1: 50, y0: 10, y1: 20 },
      coordinateFrame: { space: "rendered_page_pixels", pageWidth: 1000, pageHeight: 2000, rotation: 0, transformVersion: "identity" } };
    row[field] = null;
    render(<FrozenReviewEvidence context={context} locators={[row]} title="页级定位" onClose={vi.fn()} />);
    await screen.findByRole("navigation");
    expect(screen.getByRole("status")).toHaveTextContent("仅定位到所在页面，未标注具体区域");
  });

  it("身份不一致时不显示提示或借用其他原件", async () => {
    mocks.snapshot.mockResolvedValue({ ...shared, subjectId: "other-subject", members: [] });
    render(<FrozenReviewEvidence context={context} locators={[locator]} title="原件" onClose={vi.fn()} />);
    expect(await screen.findByRole("alert")).toHaveTextContent("原件与本次审核保存的出处不一致");
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    expect(mocks.viewer).not.toHaveBeenCalled();
  });

  it("关闭和Esc仍走现有操作，卸载后恢复原按钮焦点", async () => {
    const close = vi.fn();
    const trigger = document.createElement("button"); document.body.append(trigger); trigger.focus();
    const view = render(<FrozenReviewEvidence context={context} locators={[locator]} title="原件" onClose={close} />);
    await screen.findByRole("navigation");
    fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true, cancelable: true }));
    expect(close).toHaveBeenCalledOnce();
    view.unmount(); expect(trigger).toHaveFocus(); trigger.remove();
  });
});
