import { X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { getEvidenceRepository } from "../../api/evidence";
import type { LocatorView } from "../../api/evidence";
import type { ReviewHistoryContextView } from "../../api/review-history/reviewHistoryTypes";
import { useLoad } from "../../app/useLoad";
import { OriginalEvidenceViewer } from "../evidence-workspace/OriginalEvidenceViewer";
import { ErrorState, LoadingState } from "../shell/Feedback";

interface Props {
  context: Pick<ReviewHistoryContextView, "projectId" | "subjectId" | "reviewEpisodeId" | "completeProcessingRevisionId" | "evidenceSnapshotV2Id">;
  locators: LocatorView[];
  title: string;
  onClose: () => void;
}

export function FrozenReviewEvidence({ context, locators, title, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [selection, setSelection] = useState({ locatorId: locators[0]?.locatorId ?? null, sequence: 0 });
  const [scrolledEntry, setScrolledEntry] = useState<string | null>(null);
  const sources = useLoad(async (signal) => {
    const repository = getEvidenceRepository();
    const [revision, snapshot] = await Promise.all([
      repository.getProcessingRevision(context.completeProcessingRevisionId, { signal }),
      repository.getEvidenceSnapshot(context.evidenceSnapshotV2Id, { signal }),
    ]);
    return { revision, snapshot };
  }, [context.completeProcessingRevisionId, context.evidenceSnapshotV2Id]);
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement;
    element?.showModal();
    return () => {
      element?.close();
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, []);
  const data = sources.state.status === "success" ? sources.state.data : null;
  const bound = data !== null
    && data.revision.revisionId === context.completeProcessingRevisionId
    && data.revision.evidenceSnapshotId === context.evidenceSnapshotV2Id
    && data.snapshot.evidenceSnapshotId === context.evidenceSnapshotV2Id
    && [data.revision, data.snapshot].every((item) => item.subjectId === context.subjectId
      && item.projectId === context.projectId && item.reviewEpisodeId === context.reviewEpisodeId);
  const pages = bound && data !== null ? data.revision.pages : [];
  const consistent = locators.every((locator) => pages.some((page) =>
    page.pageArtifactId === locator.pageArtifactId && page.sourceDocumentVersionId === locator.sourceDocumentVersionId
      && page.pageNumber === locator.pageNumber));
  const names = new Map(bound && data !== null
    ? data.snapshot.members.map((member) => [member.sourceDocumentVersionId, member.fileName]) : []);
  const selected = locators.find((item) => item.locatorId === selection.locatorId);
  const selectedPage = pages.find((page) => page.pageArtifactId === selected?.pageArtifactId
    && page.sourceDocumentVersionId === selected?.sourceDocumentVersionId && page.pageNumber === selected?.pageNumber);
  return <dialog ref={dialog} className="review-source-dialog" aria-labelledby={titleId}
    onCancel={(event) => { event.preventDefault(); onClose(); }}>
    <header className="review-source-dialog__head"><h2 id={titleId}>{title}</h2>
      <button type="button" className="icon-button" onClick={onClose} aria-label="关闭原始资料" title="关闭原始资料"><X aria-hidden="true" /></button>
    </header>
    {sources.state.status === "loading" ? <LoadingState /> : sources.state.status === "error"
      ? <ErrorState message={sources.state.message} onRetry={sources.retry} />
      : !bound || !consistent ? <p role="alert">原件与本次审核保存的出处不一致，暂不能定位；系统未改用其他资料。</p>
      : <div className="review-source-dialog__body">
        <nav className="review-source-dialog__refs" aria-label="本条审核的原文摘录">
          {locators.map((locator) => <button key={locator.locatorId} type="button"
            aria-current={selection.locatorId === locator.locatorId ? "true" : undefined}
            onClick={() => { setSelection((previous) => ({ locatorId: locator.locatorId, sequence: previous.sequence + 1 })); setScrolledEntry(null); }}>
            <strong>{names.get(locator.sourceDocumentVersionId) ?? "原始资料"} · 第 {locator.pageNumber} 页</strong>
            <span>{locator.excerpt?.trim() || "该出处未保存文字摘录，请核对原件。"}</span>
            <small>{locator.precision === "bbox" && locator.authenticity === "authenticated"
              ? "已标出原文位置" : "仅定位到所在页面，未标注具体区域"}</small>
          </button>)}
        </nav>
        <OriginalEvidenceViewer revisionId={context.completeProcessingRevisionId} pages={pages} documentNames={names}
          selectedEntryId={scrolledEntry ?? selectedPage?.entryId ?? null} selectedLocatorId={selection.locatorId}
          selectedPageLocators={locators} navigationKey={`${selection.locatorId}:${selection.sequence}`}
          onSelectPage={setScrolledEntry} unavailableRecoveryHint="原审核结果保留；本次原件暂不可显示，未替换为后续上传版本。" />
      </div>}
  </dialog>;
}
