import { Save, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { getCatalogRepository } from "../../api";
import { getEvidenceRepository, type LocatorView } from "../../api/evidence";
import { createReviewActionHttp } from "../../api/review-history/reviewActionHttp";
import type { ReviewHistoryActionView, ReviewHistoryContextView } from "../../api/review-history/reviewHistoryTypes";
import { useLoad } from "../../app/useLoad";
import { OriginalEvidenceViewer } from "../evidence-workspace/OriginalEvidenceViewer";
import { ErrorState, LoadingState } from "../shell/Feedback";

const commands = createReviewActionHttp();
interface Props {
  action: ReviewHistoryActionView;
  context: ReviewHistoryContextView;
  onClose: () => void;
  onSaved: () => void;
}

export function ReviewActionResponseDialog({ action, context, onClose, onSaved }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const [reason, setReason] = useState("");
  const [selectedEntry, setSelectedEntry] = useState<string | null>(null);
  const [selectedLocators, setSelectedLocators] = useState<LocatorView[]>([]);
  const [focusedLocator, setFocusedLocator] = useState<string | null>(null);
  const [navigation, setNavigation] = useState(0);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const intent = useRef<{ content: string; key: string } | null>(null);
  const reopen = action.state === "closed_manual";
  const sources = useLoad(async (signal) => {
    const episodes = await getCatalogRepository().listEpisodes(context.subjectId, signal);
    const episode = episodes.find((item) => item.reviewEpisodeId === context.reviewEpisodeId);
    if (!episode || episode.activeEvidenceSnapshotId === null || episode.activeEvidenceProcessingRevisionId === null) return null;
    const repository = getEvidenceRepository();
    const [revision, snapshot] = await Promise.all([
      repository.getProcessingRevision(episode.activeEvidenceProcessingRevisionId, { signal }),
      repository.getEvidenceSnapshot(episode.activeEvidenceSnapshotId, { signal }),
    ]);
    if (revision.revisionId !== episode.activeEvidenceProcessingRevisionId || snapshot.evidenceSnapshotId !== episode.activeEvidenceSnapshotId
        || revision.evidenceSnapshotId !== snapshot.evidenceSnapshotId
        || [revision, snapshot].some((item) => item.projectId !== context.projectId || item.subjectId !== context.subjectId
          || item.reviewEpisodeId !== context.reviewEpisodeId)) throw new Error("回应资料与当前审核节点不一致。");
    return { episode, revision, snapshot };
  }, [context.subjectId, context.reviewEpisodeId], { enabled: !reopen });
  const source = sources.state.status === "success" ? sources.state.data : null;
  const page = source?.revision.pages.find((item) => item.entryId === selectedEntry) ?? source?.revision.pages[0];
  const pageText = useLoad((signal) => getEvidenceRepository().getOcrPage(page?.ocrPageId ?? "",
    source?.revision.revisionId ?? "", { signal }), [page?.ocrPageId, source?.revision.revisionId],
    { enabled: !reopen && page?.ocrPageId != null });
  const currentPage = pageText.state.status === "success" && page
    && pageText.state.data.processingRevisionId === source?.revision.revisionId
    && pageText.state.data.pageArtifactId === page.pageArtifactId
    && pageText.state.data.sourceDocumentVersionId === page.sourceDocumentVersionId
    && pageText.state.data.pageNumber === page.pageNumber ? pageText.state.data : null;
  const locators = currentPage?.locators.filter((item) => item.pageArtifactId === page?.pageArtifactId
    && item.sourceDocumentVersionId === page?.sourceDocumentVersionId && item.pageNumber === page?.pageNumber
    && item.authenticity !== "rejected") ?? [];
  const selectedPageLocators = selectedLocators.filter((item) => item.pageArtifactId === page?.pageArtifactId
    && item.sourceDocumentVersionId === page?.sourceDocumentVersionId && item.pageNumber === page?.pageNumber);
  useEffect(() => {
    const element = dialog.current;
    const trigger = document.activeElement;
    element?.showModal();
    return () => { element?.close(); if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus(); };
  }, []);
  async function submit() {
    if (pending || !reason.trim() || (!reopen && (!source || selectedLocators.length === 0))) return;
    const input = {
      expected_revision: action.recordRevision, operation: reopen ? "reopen" as const : "close_manual" as const,
      reason: reason.trim(), locator_ids: reopen ? [] : selectedLocators.map((item) => item.locatorId).sort(),
      response_snapshot_id: reopen ? null : source!.snapshot.evidenceSnapshotId,
      response_processing_revision_id: reopen ? null : source!.revision.revisionId,
      expected_episode_revision: reopen ? null : source!.episode.revision,
    };
    const content = JSON.stringify(input);
    if (intent.current?.content !== content) intent.current = { content, key: crypto.randomUUID() };
    setPending(true); setError(null);
    try {
      await commands.recordResponse(context.subjectId, context.reviewEpisodeId, action.actionId,
        { ...input, idempotency_key: intent.current.key });
      onSaved();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "暂未确认保存结果，请保留说明后重试。");
    } finally { setPending(false); }
  }
  return <dialog ref={dialog} className={`review-source-dialog${reopen ? " review-source-dialog--response" : ""}`}
    aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); if (!pending) onClose(); }}>
    <header className="review-source-dialog__head"><h2 id={titleId}>{action.clause?.ruleDisplayCode ?? action.control?.displayLabel} · {reopen ? "重新办理" : "登记办结依据"}</h2>
      <button type="button" className="icon-button" disabled={pending} onClick={onClose} title="关闭" aria-label="关闭办理窗口"><X aria-hidden="true" /></button></header>
    <p>{action.requestedAction}</p><p>应提供：{action.acceptableEvidence}</p>
    <p>办理记录不改变原审核结论。补充资料后的入排结论需另行审核。</p>
    <div className="review-source-dialog__body">
      <div className="review-source-dialog__refs">
        <label className="review-response-note">办理说明<textarea value={reason} disabled={pending} rows={4}
          onChange={(event) => setReason(event.target.value)} /></label>
        {!reopen && (sources.state.status === "loading" ? <LoadingState /> : sources.state.status === "error"
          ? <ErrorState message={sources.state.message} onRetry={() => { setSelectedLocators([]); sources.retry(); }} />
          : !source ? <p>该节点尚无可选回应原件，请先补充资料。</p> : <>
            <p>已选 {selectedLocators.length} 处原件</p>
            {selectedLocators.length > 0 && <ul className="review-response-selected" aria-label="已选办理依据">
              {selectedLocators.map((locator) => <li key={locator.locatorId}>
                <button type="button" disabled={pending} onClick={() => {
                  const entry = source.revision.pages.find((item) => item.pageArtifactId === locator.pageArtifactId
                    && item.sourceDocumentVersionId === locator.sourceDocumentVersionId && item.pageNumber === locator.pageNumber);
                  if (entry) { setSelectedEntry(entry.entryId); setFocusedLocator(locator.locatorId); setNavigation((value) => value + 1); }
                }}>
                  <span>{source.snapshot.members.find((item) => item.sourceDocumentVersionId === locator.sourceDocumentVersionId)?.fileName} · 第 {locator.pageNumber} 页</span>
                  <span>{locator.excerpt?.trim() || "整页出处"}</span>
                </button>
                <button type="button" className="icon-button" disabled={pending} title="移除这处依据" aria-label="移除这处依据"
                  onClick={() => setSelectedLocators((items) => items.filter((item) => item.locatorId !== locator.locatorId))}>
                  <X size={16} aria-hidden="true" />
                </button>
              </li>)}
            </ul>}
            {pageText.state.status === "error" ? <ErrorState message={pageText.state.message} onRetry={pageText.retry} />
              : page?.ocrPageId == null ? <p>这一页尚无可保存的文字定位。</p>
              : currentPage === null ? pageText.state.status === "success"
                ? <p role="alert">这一页的原文出处与所选资料不一致，未用于办理。</p> : <LoadingState />
                : locators.length === 0 ? <p>这一页暂无可选原文出处。</p>
              : locators.map((locator) => <label className="review-response-locator" key={locator.locatorId}>
                <input type="checkbox" disabled={pending} checked={selectedLocators.some((item) => item.locatorId === locator.locatorId)}
                  onChange={(event) => {
                    const checked = event.target.checked;
                    setSelectedLocators((items) => checked ? [...items, locator] : items.filter((item) => item.locatorId !== locator.locatorId));
                    if (checked) { setFocusedLocator(locator.locatorId); setNavigation((value) => value + 1); }
                  }} />
                <span>{locator.excerpt?.trim() || `第 ${locator.pageNumber} 页（整页出处）`}</span>
              </label>)}
          </>)}
      </div>
      {!reopen && source && <OriginalEvidenceViewer revisionId={source.revision.revisionId} pages={source.revision.pages}
        documentNames={new Map(source.snapshot.members.map((item) => [item.sourceDocumentVersionId, item.fileName]))}
        selectedEntryId={page?.entryId ?? null}
        selectedLocatorId={selectedPageLocators.find((item) => item.locatorId === focusedLocator)?.locatorId ?? selectedPageLocators.at(-1)?.locatorId ?? null}
        selectedPageLocators={selectedPageLocators} navigationKey={`response:${navigation}`}
        onSelectPage={(entryId) => { if (!pending) setSelectedEntry(entryId); }} />}
    </div>
    {error && <p role="alert">{error}</p>}
    <button type="button" className="button button--primary" disabled={pending || !reason.trim() || (!reopen && selectedLocators.length === 0)} onClick={() => void submit()}>
      <Save size={16} aria-hidden="true" />{pending ? "正在保存" : reopen ? "保存重新办理记录" : "保存办结记录"}
    </button>
  </dialog>;
}
