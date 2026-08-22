import { useEffect, useMemo, useRef, useState } from "react";
import {
  conflictDifferenceRows,
  clinicalLocatorPrecisionLabel,
  isReviewableLocator,
  correctionKindLabel,
  criticalCorrectionKind,
  criticalCorrectionTextChanged,
  type CorrectionChangeKind,
  type LocatorView,
  type OcrPageView,
  type OcrRiskFlagView,
  type OcrRiskReviewDecision,
  type OcrRiskReviewView,
  type ProcessingRevisionView,
  EvidenceApiError,
} from "../../api/evidence";

export interface CorrectionDraft {
  operation: "replace" | "insert";
  textStart: number;
  textEnd: number;
  originalText: string;
  correctedText: string;
  changeKind: CorrectionChangeKind;
  reason: string;
  criticalConfirmed: boolean;
}

export interface RiskReviewDraft {
  decision: OcrRiskReviewDecision;
  reason: string;
}

export interface OcrReviewPanelProps {
  page: OcrPageView;
  revision: ProcessingRevisionView;
  conflict: EvidenceApiError | null;
  isCurrentRevision?: boolean;
  editingDisabledReason?: string | null;
  onSubmitCorrection: (draft: CorrectionDraft) => Promise<void>;
  onSubmitRiskReview: (
    flag: OcrRiskFlagView,
    draft: RiskReviewDraft,
  ) => Promise<void>;
  onSubmitPageRiskReview?: (scanId: string, reason: string) => Promise<void>;
  onOpenLocator: (locator: LocatorView) => void;
}

const CHANGE_KINDS: ReadonlyArray<CorrectionChangeKind> = [
  "polarity",
  "numeric",
  "decimal",
  "unit",
  "date",
  "semantic_connector",
  "other_text",
];

const RISK_DECISIONS: ReadonlyArray<{
  value: OcrRiskReviewDecision;
  label: string;
}> = [
  { value: "confirmed_as_read", label: "确认原文无误" },
  { value: "not_applicable", label: "与本页无关" },
];

function newCorrectionDraft(rawText: string): CorrectionDraft {
  const operation = rawText.length === 0 ? "insert" : "replace";
  return {
    operation,
    textStart: 0,
    textEnd: operation === "insert" ? 0 : rawText.length,
    originalText: operation === "insert" ? "" : rawText,
    correctedText: "",
    changeKind: "other_text",
    reason: "",
    criticalConfirmed: false,
  };
}

function correctionGuidance(
  draft: CorrectionDraft,
  hasCriticalChange: boolean,
): string | null {
  if (draft.correctedText.trim().length === 0)
    return draft.operation === "insert"
      ? "请填写需要补入的漏识别文字。"
      : "请填写校对后的文字。";
  if (draft.operation === "replace" && draft.correctedText === draft.originalText)
    return "校对后的文字与原文相同，无需提交。";
  if (draft.reason.trim().length === 0) return "请说明需要校对的原因。";
  if (hasCriticalChange && !draft.criticalConfirmed)
    return "请逐字核对并确认这项关键语义变化。";
  return null;
}

function riskReviewFor(
  reviews: OcrRiskReviewView[],
  flag: OcrRiskFlagView,
): OcrRiskReviewView | undefined {
  return reviews
    .filter((review) => review.riskFlagId === flag.riskFlagId)
    .sort((left, right) =>
      `${right.createdAt}:${right.reviewId}`.localeCompare(
        `${left.createdAt}:${left.reviewId}`,
      ),
    )[0];
}

function correctionResolvesFlag(
  correction: OcrPageView["selectedCorrections"][number],
  flag: OcrRiskFlagView,
  pageTextLength: number,
): boolean {
  if (flag.kind === "output_repetition") {
    return correction.textStart === 0 && correction.textEnd === pageTextLength;
  }
  if (correction.textStart === correction.textEnd) {
    return (
      flag.textStart < correction.textStart &&
      correction.textStart < flag.textEnd
    );
  }
  return (
    Math.max(correction.textStart, flag.textStart) <
    Math.min(correction.textEnd, flag.textEnd)
  );
}

function ConflictNotice({ error }: { error: EvidenceApiError }) {
  const rows = conflictDifferenceRows(error.conflictContext);
  return (
    <section
      className="evidence-conflict-notice"
      role="alert"
      aria-label="资料已发生变化"
    >
      <h4 className="evidence-conflict-notice__title">{error.title}</h4>
      <p>{error.message}</p>
      {rows.length > 0 && (
        <div className="evidence-conflict-notice__table-wrap">
          <table className="evidence-conflict-notice__table">
            <caption>本次输入与系统当前记录的差异</caption>
            <thead>
              <tr>
                <th scope="col">项目</th>
                <th scope="col">本次输入</th>
                <th scope="col">系统当前记录</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.field}>
                  <th scope="row">{row.field}</th>
                  <td>{row.submitted}</td>
                  <td>{row.current}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="evidence-conflict-notice__recovery">
        {error.recoveryAction}
      </p>
      <p className="evidence-conflict-notice__keep">
        本次输入仍保留，请核对差异后再决定是否提交。
      </p>
    </section>
  );
}

function LocatorList({
  locators,
  onOpenLocator,
}: {
  locators: LocatorView[];
  onOpenLocator: (locator: LocatorView) => void;
}) {
  const reviewableLocators = locators.filter(isReviewableLocator);
  if (reviewableLocators.length === 0) {
    return <p className="evidence-subtle">本页暂无可展示的证据定位。</p>;
  }
  return (
    <ul className="evidence-locator-list">
      {reviewableLocators.map((locator) => (
        <li key={locator.locatorId} className="evidence-locator-list__item">
          <div className="evidence-locator-list__head">
            <strong>{locator.excerpt === null ? "本页定位" : `“${locator.excerpt}”`}</strong>
            <span className="chip">
              {clinicalLocatorPrecisionLabel(locator.precision)}
            </span>
          </div>
          {locator.precision !== "bbox" &&
            locator.degradationReason !== null && (
              <p className="evidence-locator-list__degraded">
                当前只能按较粗范围查看：{locator.degradationReason}
              </p>
            )}
          {locator.precision === "bbox" &&
            locator.authenticity !== "authenticated" && (
              <p className="evidence-locator-list__degraded">
                当前无法可靠标出原文位置，暂不显示重点框。
              </p>
            )}
          <button
            type="button"
            className="button evidence-locator-list__open"
            onClick={() => onOpenLocator(locator)}
          >
            在原件中查看
          </button>
        </li>
      ))}
    </ul>
  );
}

export function OcrReviewPanel({
  page,
  revision,
  conflict,
  isCurrentRevision = false,
  editingDisabledReason = null,
  onSubmitCorrection,
  onSubmitRiskReview,
  onSubmitPageRiskReview = async () => undefined,
  onOpenLocator,
}: OcrReviewPanelProps) {
  const rawTextRef = useRef<HTMLPreElement>(null);
  const [correction, setCorrection] = useState<CorrectionDraft>(() =>
    newCorrectionDraft(page.rawText),
  );
  const [correctionBusy, setCorrectionBusy] = useState(false);
  const [riskDrafts, setRiskDrafts] = useState<Record<string, RiskReviewDraft>>(
    {},
  );
  const [riskBusy, setRiskBusy] = useState<string | null>(null);
  const [pageReviewConfirmed, setPageReviewConfirmed] = useState(false);
  const [pageReviewBusy, setPageReviewBusy] = useState(false);

  const rangeOptions = useMemo(() => {
    const options = [
      {
        key: "page",
        label: "整页文字",
        textStart: 0,
        textEnd: page.rawText.length,
        originalText: page.rawText,
      },
      ...page.riskScans.flatMap((scan) =>
        scan.flags.map((flag) => ({
          key: flag.riskFlagId,
          label: `${flag.kindLabel}：“${flag.text}”`,
          textStart: flag.textStart,
          textEnd: flag.textEnd,
          originalText: flag.text,
        })),
      ),
    ];
    return options.filter(
      (option, index, all) =>
        all.findIndex((item) => item.key === option.key) === index,
    );
  }, [page.rawText, page.riskScans]);

  const allFlags = page.riskScans.flatMap((scan) => scan.flags);
  const reviewedRiskIds = new Set(
    page.riskReviews.map((review) => review.riskFlagId),
  );
  const isWholePageCorrection = page.selectedCorrections.some(
    (correction) =>
      correction.textStart === 0 && correction.textEnd === page.rawText.length,
  );
  const severeQualityFlags = allFlags.filter(
    (flag) => flag.kind === "output_repetition",
  );
  const pendingFlags = allFlags.filter((flag) => {
    if (flag.kind === "output_repetition") return !isWholePageCorrection;
    const corrected = page.selectedCorrections.some(
      (correction) => correctionResolvesFlag(correction, flag, page.rawText.length),
    );
    return !reviewedRiskIds.has(flag.riskFlagId) && !corrected;
  });
  const pendingRiskCount = pendingFlags.length;
  const pageReviewScan =
    page.riskScans.length === 1 && severeQualityFlags.length === 0
      ? page.riskScans[0]
      : null;
  const reviewableLocators = page.locators.filter(isReviewableLocator);
  const locatableRiskIds = new Set(
    reviewableLocators
      .map((locator) => locator.targetId)
      .filter((targetId) => allFlags.some((flag) => flag.riskFlagId === targetId)),
  );
  const currentPagePosition =
    revision.pages.findIndex((entry) => entry.ocrPageId === page.ocrPageId) + 1;
  const [showCorrectionTools, setShowCorrectionTools] =
    useState(!isCurrentRevision);
  const [showRiskDetails, setShowRiskDetails] = useState(
    !isCurrentRevision || pendingRiskCount > 0,
  );
  const [showLocatorDetails, setShowLocatorDetails] =
    useState(!isCurrentRevision);
  const pageReviewStatus =
    pendingRiskCount > 0
      ? `文字已识别 · ${pendingRiskCount} 项待核对`
      : allFlags.length > 0
        ? "文字已识别 · 风险已核对"
        : page.statusLabel;
  const selectedRangeKey = rangeOptions.find(
    (option) =>
      option.textStart === correction.textStart &&
      option.textEnd === correction.textEnd &&
      option.originalText === correction.originalText,
  )?.key;
  const selectedInsertionKey =
    correction.operation !== "insert"
      ? null
      : correction.textStart === 0
        ? "start"
        : correction.textStart === page.rawText.length
          ? "end"
          : "cursor";
  const insertionPositionLabel =
    correction.textStart === 0
      ? "当前页识别文字开头"
      : correction.textStart === page.rawText.length
        ? "当前页识别文字末尾"
        : "原文中已选位置";
  const hasCriticalChange =
    criticalCorrectionKind(correction.changeKind) ||
    criticalCorrectionTextChanged(
      correction.originalText,
      correction.correctedText,
    );
  const guidance = correctionGuidance(correction, hasCriticalChange);
  const correctionValid =
    editingDisabledReason === null &&
    correction.correctedText.trim().length > 0 &&
    correction.correctedText !== correction.originalText &&
    correction.reason.trim().length > 0 &&
    (!hasCriticalChange || correction.criticalConfirmed);
  const hasUnsavedChanges =
    correction.correctedText.trim().length > 0 ||
    correction.reason.trim().length > 0 ||
    correction.criticalConfirmed ||
    Object.values(riskDrafts).some(
      (draft) =>
        draft.reason.trim().length > 0 ||
        draft.decision !== "confirmed_as_read",
    );

  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const message = "当前页面有尚未提交的核对内容，确定离开吗？";
    const beforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    const protectInternalNavigation = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const anchor = target.closest<HTMLAnchorElement>("a[href]");
      if (anchor === null || anchor.target === "_blank") return;
      if (!window.confirm(message)) {
        event.preventDefault();
        event.stopImmediatePropagation();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("click", protectInternalNavigation, true);
    return () => {
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("click", protectInternalNavigation, true);
    };
  }, [hasUnsavedChanges]);

  function openSection(sectionId: string) {
    window.requestAnimationFrame(() => {
      document.getElementById(sectionId)?.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    });
  }

  async function submitCorrection() {
    if (!correctionValid || correctionBusy) return;
    setCorrectionBusy(true);
    try {
      await onSubmitCorrection(correction);
      setCorrection(newCorrectionDraft(page.rawText));
    } catch {
      // 409 或网络失败时保留编辑内容，由父级提供错误差异。
    } finally {
      setCorrectionBusy(false);
    }
  }

  function chooseRange(key: string) {
    const option = rangeOptions.find((item) => item.key === key);
    if (option === undefined) return;
    setCorrection((current) => ({
      ...current,
      operation: "replace",
      textStart: option.textStart,
      textEnd: option.textEnd,
      originalText: option.originalText,
      correctedText: "",
      criticalConfirmed: false,
    }));
  }

  function chooseOperation(operation: CorrectionDraft["operation"]) {
    setCorrection((current) => ({
      ...current,
      operation,
      textStart: operation === "insert" ? page.rawText.length : 0,
      textEnd: page.rawText.length,
      originalText: operation === "insert" ? "" : page.rawText,
      correctedText: "",
      criticalConfirmed: false,
    }));
  }

  function chooseInsertionPosition(position: "start" | "end" | "cursor") {
    const textStart =
      position === "start"
        ? 0
        : position === "end"
          ? page.rawText.length
          : correction.textStart;
    setCorrection((current) => ({
      ...current,
      operation: "insert",
      textStart,
      textEnd: textStart,
      originalText: "",
      correctedText: "",
      criticalConfirmed: false,
    }));
  }

  function chooseBrowserSelection() {
    const container = rawTextRef.current;
    const selection = window.getSelection();
    if (
      container === null ||
      selection === null ||
      selection.rangeCount === 0
    ) {
      return;
    }
    const range = selection.getRangeAt(0);
    if (
      !container.contains(range.startContainer) ||
      !container.contains(range.endContainer)
    ) {
      return;
    }
    const prefix = range.cloneRange();
    prefix.selectNodeContents(container);
    prefix.setEnd(range.startContainer, range.startOffset);
    const textStart = prefix.toString().length;
    const originalText = range.toString();
    const textEnd = textStart + originalText.length;
    if (page.rawText.slice(textStart, textEnd) !== originalText) {
      return;
    }
    setCorrection((current) => ({
      ...current,
      operation: originalText.length === 0 ? "insert" : "replace",
      textStart,
      textEnd,
      originalText,
      correctedText: "",
      criticalConfirmed: false,
    }));
  }

  function riskDraftFor(flag: OcrRiskFlagView): RiskReviewDraft {
    return (
      riskDrafts[flag.riskFlagId] ?? {
        decision: "confirmed_as_read",
        reason: "",
      }
    );
  }

  async function submitRisk(flag: OcrRiskFlagView) {
    const draft = riskDraftFor(flag);
    if (draft.reason.trim().length === 0 || riskBusy !== null) return;
    setRiskBusy(flag.riskFlagId);
    try {
      await onSubmitRiskReview(flag, draft);
      setRiskDrafts((current) => {
        const next = { ...current };
        delete next[flag.riskFlagId];
        return next;
      });
    } catch {
      // 409 时保留本风险条目的选择和说明。
    } finally {
      setRiskBusy(null);
    }
  }

  async function submitPageReview() {
    if (
      pageReviewScan === null ||
      !pageReviewConfirmed ||
      pageReviewBusy ||
      editingDisabledReason !== null
    )
      return;
    setPageReviewBusy(true);
    try {
      await onSubmitPageRiskReview(
        pageReviewScan.scanId,
        "已对照右侧原件逐项核对本页识别内容",
      );
      setPageReviewConfirmed(false);
    } finally {
      setPageReviewBusy(false);
    }
  }

  return (
    <div className="evidence-review-panel">
      {conflict !== null && <ConflictNotice error={conflict} />}
      <nav className="evidence-review-nav" aria-label="本页核对内容快捷入口">
        <button type="button" onClick={() => openSection("evidence-text")}>
          识别文本
        </button>
        <button
          type="button"
          onClick={() => openSection("evidence-correction")}
        >
          文字校对
        </button>
        <button
          type="button"
          onClick={() => openSection("evidence-risks")}
        >
          风险核对
          {pendingRiskCount > 0 ? `（${pendingRiskCount} 项待处理）` : ""}
        </button>
        <button
          type="button"
          onClick={() => openSection("evidence-locators")}
        >
          原件定位
        </button>
      </nav>
      <section
        id="evidence-text"
        className="evidence-text-section"
        aria-label="原始识别与校对后文本"
      >
        <div className="evidence-panel-heading">
          <div>
            <p className="evidence-kicker">第 {page.pageNumber} 页</p>
            <h4>原始识别 / 校对后文本</h4>
          </div>
          <span className="chip">{pageReviewStatus}</span>
        </div>
        <div className="evidence-text-pair">
          <article className="evidence-text-pane evidence-text-pane--source">
            <div className="evidence-text-pane__head">
              <h5>原始识别</h5>
              <span>原始记录</span>
            </div>
            <pre
              ref={rawTextRef}
              tabIndex={0}
              onMouseUp={chooseBrowserSelection}
              onKeyUp={chooseBrowserSelection}
            >
              {page.rawText}
            </pre>
          </article>
          <article className="evidence-text-pane evidence-text-pane--effective">
            <div className="evidence-text-pane__head">
              <h5>校对后文本</h5>
              <span>审核使用</span>
            </div>
            {page.effectiveText === null ? (
              <p className="evidence-text-empty">
                尚未形成校对文本。可在下方修正已识别文字，或补入漏识别文字。
              </p>
            ) : (
              <pre>{page.effectiveText}</pre>
            )}
          </article>
        </div>
      </section>

      <section
        id="evidence-correction"
        className="evidence-correction-section"
        aria-label="文字校对"
      >
        <div className="evidence-panel-heading">
          <div>
            <p className="evidence-kicker">追加校对</p>
            <h4>校对原始识别文本</h4>
          </div>
          <div className="evidence-panel-heading__actions">
            <span className="evidence-subtle">
              {isCurrentRevision
                ? "当前有效资料；新校对需重新生成并启用"
                : `资料状态：${revision.statusLabel}`}
            </span>
            {isCurrentRevision && (
              <button
                type="button"
                className="button"
                aria-expanded={showCorrectionTools}
                onClick={() => setShowCorrectionTools((value) => !value)}
              >
                {showCorrectionTools ? "收起校对工具" : "需要修订识别文字"}
              </button>
            )}
          </div>
        </div>
        {showCorrectionTools && (
          <>
            {editingDisabledReason !== null && (
              <p className="evidence-form-guidance" role="status">
                {editingDisabledReason}
              </p>
            )}
            <div className="evidence-form-grid">
              <fieldset className="evidence-correction-mode">
                <legend>校对方式</legend>
                <div className="evidence-correction-mode__options">
                  <button
                    type="button"
                    aria-pressed={correction.operation === "replace"}
                    disabled={page.rawText.length === 0}
                    onClick={() => chooseOperation("replace")}
                  >
                    修正已识别文字
                  </button>
                  <button
                    type="button"
                    aria-pressed={correction.operation === "insert"}
                    onClick={() => chooseOperation("insert")}
                  >
                    补入漏识别文字
                  </button>
                </div>
              </fieldset>
              {correction.operation === "replace" ? (
                <label>
                  原文范围
                  <select
                    value={selectedRangeKey ?? "selection"}
                    onChange={(event) => chooseRange(event.target.value)}
                  >
                    {selectedRangeKey === undefined && (
                      <option value="selection">已拖选的原文</option>
                    )}
                    {rangeOptions.map((option) => (
                      <option key={option.key} value={option.key}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <label>
                  插入位置
                  <select
                    value={selectedInsertionKey ?? "end"}
                    onChange={(event) =>
                      chooseInsertionPosition(
                        event.target.value as "start" | "end" | "cursor",
                      )
                    }
                  >
                    <option value="start">当前页识别文字开头</option>
                    {selectedInsertionKey === "cursor" && (
                      <option value="cursor">原文中已选位置</option>
                    )}
                    <option value="end">当前页识别文字末尾</option>
                  </select>
                </label>
              )}
              <label>
                变化类别
                <select
                  value={correction.changeKind}
                  onChange={(event) =>
                    setCorrection((current) => ({
                      ...current,
                      changeKind: event.target.value as CorrectionChangeKind,
                      criticalConfirmed: false,
                    }))
                  }
                >
                  {CHANGE_KINDS.map((kind) => (
                    <option key={kind} value={kind}>
                      {correctionKindLabel(kind)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="evidence-selected-excerpt">
              {correction.operation === "insert" ? (
                <>
                  <span>插入位置</span>
                  <strong>{insertionPositionLabel}</strong>
                </>
              ) : (
                <>
                  <span>选中的原文</span>
                  <q>{correction.originalText || "尚未选择"}</q>
                </>
              )}
            </div>
            <label className="evidence-field evidence-field--wide">
              {correction.operation === "insert"
                ? "补入的漏识别文字"
                : "校对后文本"}
              <textarea
                disabled={editingDisabledReason !== null}
                value={correction.correctedText}
                onChange={(event) =>
                  setCorrection((current) => ({
                    ...current,
                    correctedText: event.target.value,
                    criticalConfirmed: false,
                  }))
                }
                rows={4}
                placeholder={
                  correction.operation === "insert"
                    ? "请输入原件中漏识别的文字"
                    : "请输入校对后的文字"
                }
              />
            </label>
            <label className="evidence-field evidence-field--wide">
              校对说明
              <textarea
                disabled={editingDisabledReason !== null}
                value={correction.reason}
                onChange={(event) =>
                  setCorrection((current) => ({
                    ...current,
                    reason: event.target.value,
                  }))
                }
                rows={2}
                placeholder="说明为何需要这次校对"
              />
            </label>
            {hasCriticalChange && (
              <label className="evidence-critical-confirmation">
                <input
                  type="checkbox"
                  disabled={editingDisabledReason !== null}
                  checked={correction.criticalConfirmed}
                  onChange={(event) =>
                    setCorrection((current) => ({
                      ...current,
                      criticalConfirmed: event.target.checked,
                    }))
                  }
                />
                <span>我已逐字核对这项关键变化，并确认它会影响临床语义。</span>
              </label>
            )}
            <button
              type="button"
              className="button button--primary"
              disabled={!correctionValid || correctionBusy}
              onClick={() => void submitCorrection()}
            >
              {correctionBusy
                ? "正在提交…"
                : correction.operation === "insert"
                  ? "提交补入文字"
                  : "提交校对"}
            </button>
            {!correctionBusy &&
              editingDisabledReason === null &&
              guidance !== null && (
                <p className="evidence-form-guidance" role="status">
                  {guidance}
                </p>
              )}
          </>
        )}
      </section>

      <section
        id="evidence-risks"
        className="evidence-risk-section"
        aria-label="识别风险核对"
      >
        <div className="evidence-review-context" role="note">
          <p>
            本资料版本共 {revision.pages.length} 页，当前为第{" "}
            {currentPagePosition > 0 ? currentPagePosition : page.pageNumber} 页。
            当前页发现 {allFlags.length} 个风险片段，其中 {locatableRiskIds.size}
            个可在原件中定位；尚有 {pendingRiskCount} 个待核对。
          </p>
          <p>
            全版本共发现 {revision.riskFlagCount} 个风险片段，尚有{" "}
            {revision.pendingRiskFlagCount} 个待核对。“风险片段数”按识别文字中的待核对内容统计，“可定位片段数”按已核验的原件位置统计，两者口径不同。
          </p>
        </div>
        <div className="evidence-panel-heading">
          <div>
            <p className="evidence-kicker">风险核对</p>
            <h4>
              {pendingRiskCount > 0
                ? `还有 ${pendingRiskCount} 项待核对`
                : "本页识别风险已核对"}
            </h4>
          </div>
          <div className="evidence-panel-heading__actions">
            <span className="section-count">{allFlags.length}</span>
            {pendingRiskCount === 0 && allFlags.length > 0 && (
              <button
                type="button"
                className="button"
                aria-expanded={showRiskDetails}
                onClick={() => setShowRiskDetails((value) => !value)}
              >
                {showRiskDetails
                  ? "收起核对记录"
                  : `查看 ${allFlags.length} 项核对记录`}
              </button>
            )}
          </div>
        </div>
        {allFlags.length === 0 ? (
          <p className="evidence-subtle">本页暂无结构化识别核对提示。</p>
        ) : !showRiskDetails ? (
          <p className="evidence-section-summary">
            {allFlags.length} 项识别风险均已核对；需要复查时再展开逐项记录。
          </p>
        ) : (
          <>
          {severeQualityFlags.length > 0 && !isWholePageCorrection ? (
            <div className="evidence-risk-quality-alert" role="alert">
              <strong>本页识别内容异常重复，不能直接确认</strong>
              <p>请重新识别；若仍无法获得可靠结果，请对照右侧原件校对整页文字。</p>
            </div>
          ) : pageReviewScan !== null && pendingRiskCount > 0 ? (
            <div className="evidence-page-review">
              <label>
                <input
                  type="checkbox"
                  checked={pageReviewConfirmed}
                  disabled={editingDisabledReason !== null || pageReviewBusy}
                  onChange={(event) => setPageReviewConfirmed(event.target.checked)}
                />
                <span>我已对照右侧原件逐项核对本页识别内容</span>
              </label>
              <button
                type="button"
                className="button button--primary"
                disabled={
                  editingDisabledReason !== null ||
                  !pageReviewConfirmed ||
                  pageReviewBusy
                }
                onClick={() => void submitPageReview()}
              >
                {pageReviewBusy ? "正在保存…" : `确认本页 ${pendingRiskCount} 项`}
              </button>
            </div>
          ) : null}
          <ul className="evidence-risk-list">
            {allFlags.map((flag) => {
              const existing = riskReviewFor(page.riskReviews, flag);
              const draft = riskDraftFor(flag);
              const hasCoveringCorrection =
                page.selectedCorrections.some((correction) =>
                  correctionResolvesFlag(correction, flag, page.rawText.length),
                );
              const requiresReprocessing =
                flag.kind === "output_repetition" && !hasCoveringCorrection;
              return (
                <li
                  key={flag.riskFlagId}
                  className={`evidence-risk-item evidence-risk-item--${flag.level}`}
                >
                  <div className="evidence-risk-item__head">
                    <strong>{flag.kindLabel}</strong>
                    <span className="chip">{flag.levelLabel}</span>
                  </div>
                  <p className="evidence-risk-item__text">“{flag.text}”</p>
                  {flag.detail !== null && (
                    <p className="evidence-subtle">{flag.detail}</p>
                  )}
                  {existing !== undefined && (
                    <p className="evidence-risk-item__reviewed">
                      已核对：{existing.decisionLabel}。{existing.reason}
                    </p>
                  )}
                  {hasCoveringCorrection ? (
                    <p className="evidence-risk-item__reviewed">
                      已通过文字校对解除，请以校对后文本为准。
                    </p>
                  ) : requiresReprocessing ? (
                    <p className="evidence-risk-item__required-action">
                      此项反映整页识别质量，不能用人工确认解除。
                    </p>
                  ) : (
                  <div className="evidence-risk-item__actions">
                    <select
                      aria-label={`${flag.kindLabel}的核对决定`}
                      value={draft.decision}
                      onChange={(event) =>
                        setRiskDrafts((current) => ({
                          ...current,
                          [flag.riskFlagId]: {
                            ...draft,
                            decision: event.target
                              .value as OcrRiskReviewDecision,
                          },
                        }))
                      }
                    >
                      {RISK_DECISIONS.map((decision) => (
                        <option key={decision.value} value={decision.value}>
                          {decision.label}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label={`${flag.kindLabel}的核对说明`}
                      value={draft.reason}
                      onChange={(event) =>
                        setRiskDrafts((current) => ({
                          ...current,
                          [flag.riskFlagId]: {
                            ...draft,
                            reason: event.target.value,
                          },
                        }))
                      }
                      placeholder="核对说明（必填）"
                      disabled={editingDisabledReason !== null}
                    />
                    <button
                      type="button"
                      className="button"
                      disabled={
                        editingDisabledReason !== null ||
                        draft.reason.trim().length === 0 ||
                        riskBusy !== null
                      }
                      onClick={() => void submitRisk(flag)}
                    >
                      {riskBusy === flag.riskFlagId
                        ? "正在提交…"
                        : existing === undefined
                          ? "保存核对"
                          : "重新核对"}
                    </button>
                    {editingDisabledReason === null &&
                      draft.reason.trim().length === 0 && (
                        <p className="evidence-form-guidance" role="status">
                          填写核对说明后可保存。
                        </p>
                      )}
                  </div>
                  )}
                </li>
              );
            })}
          </ul>
          </>
        )}
      </section>

      <section
        id="evidence-locators"
        className="evidence-locator-section"
        aria-label="证据定位精度"
      >
        <div className="evidence-panel-heading">
          <div>
            <p className="evidence-kicker">证据定位</p>
            <h4>实际定位精度</h4>
          </div>
          <div className="evidence-panel-heading__actions">
            <span className="evidence-subtle">仅展示已核验的真实定位</span>
            {isCurrentRevision && reviewableLocators.length > 0 && (
              <button
                type="button"
                className="button"
                aria-expanded={showLocatorDetails}
                onClick={() => setShowLocatorDetails((value) => !value)}
              >
                {showLocatorDetails
                  ? "收起定位清单"
                  : `查看 ${reviewableLocators.length} 处原件定位`}
              </button>
            )}
          </div>
        </div>
        {showLocatorDetails ? (
          <LocatorList locators={reviewableLocators} onOpenLocator={onOpenLocator} />
        ) : (
          <p className="evidence-section-summary">
            原件定位已保存；展开后可逐项跳转并核对红框位置。
          </p>
        )}
      </section>
    </div>
  );
}
