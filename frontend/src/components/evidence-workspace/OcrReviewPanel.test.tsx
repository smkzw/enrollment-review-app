// @vitest-environment jsdom

import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  EvidenceApiError,
  decodeOcrPage,
  decodeProcessingRevision,
} from "../../api/evidence";
import { OcrReviewPanel, type CorrectionDraft } from "./OcrReviewPanel";

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

function page() {
  return decodeOcrPage({
    ocr_page_id: "ocr-page-1",
    page_artifact_id: "artifact-1",
    source_document_version_id: "version-1",
    page_number: 1,
    source_sha256: "a".repeat(64),
    raw_text: "患者否认发热。",
    raw_text_sha256: "b".repeat(64),
    status: "succeeded",
    status_label: "已识别",
    processing_revision_id: "revision-1",
    is_current_revision: true,
    effective_text: null,
    effective_text_sha256: null,
    selected_corrections: [],
    risk_scans: [
      {
        scan_id: "scan-1",
        ocr_page_id: "ocr-page-1",
        raw_text_sha256: "b".repeat(64),
        scanner_rule_version: "risk-1",
        flags_sha256: "c".repeat(64),
        coverage_status: "complete",
        created_at: "2026-08-21T00:00:00Z",
        flags: [
          {
            risk_id: "risk-1",
            kind: "negation_polarity",
            kind_label: "否定/肯定",
            level: "blocking",
            level_label: "需核对",
            text: "否认",
            text_start: 2,
            text_end: 4,
            detail: "请确认否定关系。",
            rule_version: "risk-1",
          },
        ],
      },
    ],
    risk_reviews: [],
    locators: [],
  });
}

function revision() {
  return decodeProcessingRevision({
    evidence_processing_revision_id: "revision-1",
    revision_kind: "complete",
    revision_kind_label: "完整处理修订",
    evidence_snapshot_id: "snapshot-1",
    base_processing_revision_id: "base-1",
    project_id: "project-1",
    subject_id: "subject-1",
    review_episode_id: "episode-1",
    status: "active",
    status_label: "当前有效",
    is_activatable: false,
    is_current: true,
    manifest_sha256: "d".repeat(64),
    completion_manifest_sha256: null,
    pages: [
      {
        entry_id: "entry-1",
        position: 1,
        source_document_version_id: "version-1",
        page_number: 1,
        original_frame: null,
        page_artifact_id: "artifact-1",
        ocr_page_id: "ocr-page-1",
        status: "succeeded",
        status_label: "页面已就绪",
        failure_reason: null,
        image_available: true,
        page_width: 1240,
        page_height: 1754,
      },
    ],
    risk_flag_count: 12,
    pending_risk_flag_count: 7,
    locator_ids: [],
    risk_scan_ids: [],
    risk_review_ids: [],
    correction_ids: [],
    metadata_revision_ids: [],
    referenced_document_revision_ids: [],
    resolution_revision_ids: [],
    gates: [],
    created_at: "2026-08-21T00:00:00Z",
    created_by: "本地用户",
  });
}

describe("OcrReviewPanel", () => {
  it("区分文字识别完成与风险尚待核对，并提示必填说明", () => {
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );

    expect(screen.getByText("文字已识别 · 1 项待核对")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "还有 1 项待核对" }),
    ).toBeInTheDocument();
    expect(screen.getByText("填写核对说明后可保存。")).toBeInTheDocument();
    expect(
      screen.getByRole("note").textContent,
    ).toContain("本资料版本共 1 页，当前为第 1 页");
    expect(
      screen.getByRole("note").textContent,
    ).toContain("当前页发现 1 个风险片段");
    expect(
      screen.getByRole("note").textContent,
    ).toMatch(/“风险片段数”.*“可定位片段数”.*口径不同/);
    expect(screen.getByRole("note").textContent).toContain(
      "全版本共发现 12 个风险片段，尚有 7 个待核对",
    );
  });

  it("局部校对只解除实际重叠的风险片段", () => {
    const current = page();
    const scan = current.riskScans[0];
    current.riskScans = [
      {
        ...scan,
        flags: [
          scan.flags[0],
          {
            ...scan.flags[0],
            riskId: "risk-2",
            riskFlagId: "scan-1:risk-2",
            kind: "date",
            kindLabel: "日期",
            text: "发热",
            textStart: 4,
            textEnd: 6,
          },
        ],
      },
    ];
    current.selectedCorrections = [
      {
        correctionId: "correction-1",
        ocrPageId: current.ocrPageId,
        rawTextSha256: current.rawTextSha256,
        textStart: 2,
        textEnd: 3,
        originalText: "否",
        correctedText: "未",
        changeKind: "polarity",
        changeKindLabel: "否定或肯定",
        requiresConfirmation: true,
        confirmationActor: "复核人",
        confirmationAt: "2026-08-21T00:00:00Z",
        reason: "逐字核对",
        actor: "本地用户",
        baseProcessingRevisionId: "base-1",
        supersedesCorrectionId: null,
        affectedScope: [],
        createdAt: "2026-08-21T00:00:00Z",
      },
    ];

    render(
      <OcrReviewPanel
        page={current}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );

    expect(
      screen.getAllByText("已通过文字校对解除，请以校对后文本为准。"),
    ).toHaveLength(1);
    expect(
      screen.getByRole("heading", { name: "还有 1 项待核对" }),
    ).toBeInTheDocument();
  });

  it("风险片段左右边界的插入不会被误判为已解除", () => {
    const current = page();
    const flag = current.riskScans[0].flags[0];
    current.selectedCorrections = [
      {
        correctionId: "correction-boundary",
        ocrPageId: current.ocrPageId,
        rawTextSha256: current.rawTextSha256,
        textStart: flag.textEnd,
        textEnd: flag.textEnd,
        originalText: "",
        correctedText: "已",
        changeKind: "other_text",
        changeKindLabel: "其他文字",
        requiresConfirmation: false,
        confirmationActor: null,
        confirmationAt: null,
        reason: "补入相邻文字",
        actor: "本地用户",
        baseProcessingRevisionId: "base-1",
        supersedesCorrectionId: null,
        affectedScope: [],
        createdAt: "2026-08-21T00:00:00Z",
      },
    ];

    render(
      <OcrReviewPanel
        page={current}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );

    expect(
      screen.getByRole("heading", { name: "还有 1 项待核对" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("已通过文字校对解除，请以校对后文本为准。"),
    ).not.toBeInTheDocument();
  });

  it("对照右侧原件后可一次确认本页待核对项", async () => {
    const user = userEvent.setup();
    const onSubmitPageRiskReview = vi.fn(async () => undefined);
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onSubmitPageRiskReview={onSubmitPageRiskReview}
        onOpenLocator={vi.fn()}
      />,
    );

    const confirm = screen.getByRole("checkbox", {
      name: "我已对照右侧原件逐项核对本页识别内容",
    });
    const submit = screen.getByRole("button", { name: "确认本页 1 项" });
    expect(submit).toBeDisabled();
    await user.click(confirm);
    await user.click(submit);

    await waitFor(() =>
      expect(onSubmitPageRiskReview).toHaveBeenCalledWith(
        "scan-1",
        "已对照右侧原件逐项核对本页识别内容",
      ),
    );
  });

  it("整页识别异常重复时只允许重新识别或整页校对", () => {
    const current = page();
    const scan = current.riskScans[0];
    const unsafePage = {
      ...current,
      riskScans: [
        {
          ...scan,
          flags: [
            {
              ...scan.flags[0],
              riskFlagId: "scan-1:loop",
              riskId: "loop",
              kind: "output_repetition" as const,
              kindLabel: "识别内容异常重复",
              text: "结果：≤197",
              textStart: 0,
              textEnd: 7,
            },
          ],
        },
      ],
    };
    render(
      <OcrReviewPanel
        page={unsafePage}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onSubmitPageRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );

    expect(
      screen.getByText("本页识别内容异常重复，不能直接确认"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("此项反映整页识别质量，不能用人工确认解除。"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /确认本页/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "保存核对" }),
    ).not.toBeInTheDocument();
  });

  it("可直接拖选任意原始识别文字，不要求用户填写字符位置", async () => {
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );
    const raw = screen.getByText("患者否认发热。", { selector: "pre" });
    const textNode = raw.firstChild;
    if (textNode === null) throw new Error("测试原文节点缺失");
    const range = document.createRange();
    range.setStart(textNode, 4);
    range.setEnd(textNode, 6);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    raw.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));

    await waitFor(() => {
      expect(screen.getByText("发热", { selector: "q" })).toBeInTheDocument();
    });
    expect(screen.getByRole("combobox", { name: "原文范围" })).toHaveValue(
      "selection",
    );
  });

  it("可在页首补入漏识别文字，并沿用关键变化二次确认", async () => {
    const user = userEvent.setup();
    const onSubmitCorrection = vi.fn(async () => undefined);
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={onSubmitCorrection}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "补入漏识别文字" }),
    );
    const position = screen.getByRole("combobox", { name: "插入位置" });
    await user.selectOptions(position, "start");
    expect(
      screen.getByText("当前页识别文字开头", { selector: "strong" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("选中的原文")).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByRole("combobox", { name: "变化类别" }),
      "date",
    );
    await user.type(
      screen.getByRole("textbox", { name: "补入的漏识别文字" }),
      "检查日期：2026-08-21。",
    );
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "原件页首整行漏识别。",
    );
    const submit = screen.getByRole("button", { name: "提交补入文字" });
    expect(submit).toBeDisabled();
    await user.click(screen.getByRole("checkbox", { name: /关键变化/ }));
    expect(submit).toBeEnabled();
    await user.click(submit);

    await waitFor(() => expect(onSubmitCorrection).toHaveBeenCalledTimes(1));
    expect(onSubmitCorrection).toHaveBeenCalledWith(
      expect.objectContaining({
        operation: "insert",
        textStart: 0,
        textEnd: 0,
        originalText: "",
        correctedText: "检查日期：2026-08-21。",
        changeKind: "date",
        criticalConfirmed: true,
      }),
    );
  });

  it("把原始识别文字中的折叠光标用作中间插入锚点并提交零长度范围", async () => {
    const user = userEvent.setup();
    const onSubmitCorrection = vi.fn(async () => undefined);
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={onSubmitCorrection}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );
    const raw = screen.getByText("患者否认发热。", { selector: "pre" });
    const textNode = raw.firstChild;
    if (textNode === null) throw new Error("测试原文节点缺失");
    const range = document.createRange();
    range.setStart(textNode, 4);
    range.collapse(true);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
    raw.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));

    await waitFor(() =>
      expect(
        screen.getByRole("combobox", { name: "插入位置" }),
      ).toHaveValue("cursor"),
    );
    expect(
      screen.getByText("原文中已选位置", { selector: "strong" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "补入漏识别文字" }),
    ).toHaveAttribute("aria-pressed", "true");
    await user.type(
      screen.getByRole("textbox", { name: "补入的漏识别文字" }),
      "未见",
    );
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "原件中间漏识别。",
    );
    await user.click(
      screen.getByRole("checkbox", {
        name: /我已逐字核对这项关键变化/,
      }),
    );
    await user.click(screen.getByRole("button", { name: "提交补入文字" }));
    await waitFor(() => expect(onSubmitCorrection).toHaveBeenCalledTimes(1));
    expect(onSubmitCorrection).toHaveBeenCalledWith(
      expect.objectContaining({
        operation: "insert",
        textStart: 4,
        textEnd: 4,
        originalText: "",
        correctedText: "未见",
      }),
    );
  });

  it("关键变化必须二次确认，409 后保留文字、范围和确认选择，并显示系统差异", async () => {
    const user = userEvent.setup();
    const submitted: CorrectionDraft[] = [];
    const conflict = new EvidenceApiError(
      "STALE_REVISION",
      "资料已发生变化",
      "系统已有更新，请核对差异。",
      "请确认当前值后再决定是否提交。",
      409,
      {
        submitted: { corrected_text: "患者肯定发热。" },
        currentRecord: { corrected_text: "患者否认发热。" },
        fieldDiff: {
          corrected_text: {
            submitted: "患者肯定发热。",
            current: "患者否认发热。",
          },
        },
      },
    );

    function Harness() {
      const [currentConflict, setCurrentConflict] =
        useState<EvidenceApiError | null>(null);
      return (
        <OcrReviewPanel
          page={page()}
          revision={revision()}
          conflict={currentConflict}
          onSubmitCorrection={async (draft) => {
            submitted.push(draft);
            setCurrentConflict(conflict);
            throw conflict;
          }}
          onSubmitRiskReview={vi.fn(async () => undefined)}
          onOpenLocator={vi.fn()}
        />
      );
    }

    render(<Harness />);
    const changeKind = screen.getByRole("combobox", { name: "变化类别" });
    await user.selectOptions(changeKind, "polarity");
    const corrected = screen.getByRole("textbox", { name: "校对后文本" });
    await user.type(corrected, "患者肯定发热。");
    await user.type(
      screen.getByRole("textbox", { name: "校对说明" }),
      "核对报告原文后修正。",
    );
    const submit = screen.getByRole("button", { name: "提交校对" });
    expect(submit).toBeDisabled();
    const confirmation = screen.getByRole("checkbox", { name: /关键变化/ });
    await user.click(confirmation);
    expect(submit).toBeEnabled();
    await user.click(submit);

    await waitFor(() =>
      expect(
        screen.getByRole("alert", { name: "资料已发生变化" }),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getAllByRole("alert", { name: "资料已发生变化" }),
    ).toHaveLength(1);
    expect(submitted[0]?.correctedText).toBe("患者肯定发热。");
    expect(corrected).toHaveValue("患者肯定发热。");
    expect(confirmation).toBeChecked();
    expect(screen.getByText("系统当前记录")).toBeInTheDocument();
    expect(
      within(screen.getByRole("alert", { name: "资料已发生变化" })).getByText(
        "患者否认发热。",
      ),
    ).toBeInTheDocument();
  });

  it("风险核对提交真实风险标识，不把页编号作为风险标识", async () => {
    const user = userEvent.setup();
    const onSubmitRiskReview = vi.fn(async () => undefined);
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={onSubmitRiskReview}
        onOpenLocator={vi.fn()}
      />,
    );
    await user.type(
      screen.getByRole("textbox", { name: "否定/肯定的核对说明" }),
      "已核对原文。",
    );
    await user.click(screen.getByRole("button", { name: "保存核对" }));
    await waitFor(() => expect(onSubmitRiskReview).toHaveBeenCalledTimes(1));
    expect(onSubmitRiskReview).toHaveBeenCalledWith(
      expect.objectContaining({ riskFlagId: "scan-1:risk-1" }),
      expect.objectContaining({ reason: "已核对原文。" }),
    );
  });

  it("已有多次风险核对时展示最新记录，并明确这是重新核对", () => {
    const current = page();
    current.riskReviews = [
      {
        reviewId: "review-old",
        riskFlagId: "scan-1:risk-1",
        decision: "not_applicable",
        decisionLabel: "本项不适用",
        reason: "较早说明",
        actor: "本地用户",
        baseProcessingRevisionId: "revision-1",
        expectedRevision: 1,
        createdAt: "2026-08-21T08:00:00Z",
      },
      {
        reviewId: "review-new",
        riskFlagId: "scan-1:risk-1",
        decision: "confirmed_as_read",
        decisionLabel: "确认与原文一致",
        reason: "最新说明",
        actor: "本地用户",
        baseProcessingRevisionId: "revision-1",
        expectedRevision: 1,
        createdAt: "2026-08-21T09:00:00Z",
      },
    ];
    render(
      <OcrReviewPanel
        page={current}
        revision={revision()}
        conflict={null}
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );
    expect(screen.getByText(/最新说明/)).toBeInTheDocument();
    expect(screen.getByText("文字已识别 · 风险已核对")).toBeInTheDocument();
    expect(screen.queryByText(/较早说明/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "重新核对" })).toBeDisabled();
  });

  it("资料版本生成期间明确禁用校对并说明原因", () => {
    render(
      <OcrReviewPanel
        page={page()}
        revision={revision()}
        conflict={null}
        editingDisabledReason="资料版本正在生成，请完成后再校对。"
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );
    expect(
      screen.getByText("资料版本正在生成，请完成后再校对。"),
    ).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "校对后文本" })).toBeDisabled();
    expect(
      screen.getByRole("textbox", { name: "否定/肯定的核对说明" }),
    ).toBeDisabled();
  });

  it("当前有效资料默认保持阅读态，明确展开后才显示校对工具", async () => {
    const user = userEvent.setup();
    const current = page();
    current.riskReviews = [
      {
        reviewId: "review-current",
        riskFlagId: "scan-1:risk-1",
        decision: "confirmed_as_read",
        decisionLabel: "确认与原文一致",
        reason: "已核对原件。",
        actor: "本地用户",
        baseProcessingRevisionId: "revision-1",
        expectedRevision: 1,
        createdAt: "2026-08-21T09:00:00Z",
      },
    ];
    render(
      <OcrReviewPanel
        page={current}
        revision={revision()}
        conflict={null}
        isCurrentRevision
        onSubmitCorrection={vi.fn(async () => undefined)}
        onSubmitRiskReview={vi.fn(async () => undefined)}
        onOpenLocator={vi.fn()}
      />,
    );

    expect(
      screen.getByText("当前有效资料；新校对需重新生成并启用"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("textbox", { name: "校对后文本" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/1 项识别风险均已核对/)).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "文字校对" }),
    );
    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled());
    expect(
      screen.queryByRole("textbox", { name: "校对后文本" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "需要修订识别文字" }));
    const corrected = screen.getByRole("textbox", { name: "校对后文本" });
    const changeKind = screen.getByRole("combobox", { name: "变化类别" });
    expect(changeKind).toHaveValue("other_text");
    await user.type(corrected, "2026-08-22 复查");
    expect(changeKind).toHaveValue("other_text");
    expect(
      screen.getByRole("checkbox", {
        name: /我已逐字核对这项关键变化/,
      }),
    ).toBeInTheDocument();
  });

  it("存在未提交校对时阻止站内离开，并保留当前输入", async () => {
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    render(
      <>
        <OcrReviewPanel
          page={page()}
          revision={revision()}
          conflict={null}
          onSubmitCorrection={vi.fn(async () => undefined)}
          onSubmitRiskReview={vi.fn(async () => undefined)}
          onOpenLocator={vi.fn()}
        />
        <a href="/help">帮助</a>
      </>,
    );
    const corrected = screen.getByRole("textbox", { name: "校对后文本" });
    await user.type(corrected, "患者未见发热。");

    expect(fireEvent.click(screen.getByRole("link", { name: "帮助" }))).toBe(
      false,
    );
    expect(confirm).toHaveBeenCalledWith(
      "当前页面有尚未提交的核对内容，确定离开吗？",
    );
    expect(corrected).toHaveValue("患者未见发热。");
    confirm.mockRestore();
  });
});
