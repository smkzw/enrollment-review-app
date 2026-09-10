/**
 * 证据工作台（design.md §8.2/§8.3，任务 worker_03）。
 * 路由：/subjects/:subjectId/evidence?episode=<ReviewEpisodeId>。
 * - 顶部固定上下文带：项目、受试者、审核节点、方案版本、资料版本与待处理数量。
 * - 首屏二选一（补充资料 / 建立完整资料快照）+ 旁边中文说明；选择后进入确认前复核。
 * - 确认前逐文件复核：新增、重复、同名冲突、不支持、无法读取、完整资料遗漏与
 *   预计重新识别；所有同名冲突处置完成后确认才可用。
 * - 三栏宽屏工作台：左文件与页清单、中识别文本/风险核对、右连续原文件页图；
 *   仅对通过真实性核验的区域坐标绘制重点框，降级定位不画框。
 * - 取消只清理暂存，不建立任何快照。
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { getCatalogRepository, getEvidenceRepository } from "../api";
import {
  EvidenceApiError,
  EvidenceDecodeError,
  commitResultMessage,
  formatByteSize,
  type EvidenceCommitView,
  type EvidenceConflictResolution,
  type EvidenceItemView,
  type EvidenceSnapshotListView,
  type EvidenceUploadMode,
  type EvidenceUploadPreviewView,
  type OcrPageView,
  type OcrRiskFlagView,
  type ProcessingRevisionPageView,
  type ReferencedDocumentView,
  type LocatorView,
} from "../api/evidence";
import { matchRouteParams } from "../app/routes";
import { RouteLink, useHashRoute } from "../app/router";
import { useLoad, type UseLoadResult } from "../app/useLoad";
import {
  EmptyState,
  ErrorState,
  LoadingState,
} from "../components/shell/Feedback";
import { UI_PHRASES } from "../domain/labels";
import type { SubjectId } from "../domain/ids";
import { ContextBand } from "../components/evidence-workspace/ContextBand";
import { UploadModePicker } from "../components/evidence-workspace/UploadModePicker";
import { PreviewReview } from "../components/evidence-workspace/PreviewReview";
import { EvidenceWorkspace } from "../components/evidence-workspace/EvidenceWorkspace";
import { OcrReviewPanel } from "../components/evidence-workspace/OcrReviewPanel";
import { ReferencedDocumentsPanel } from "../components/evidence-workspace/ReferencedDocumentsPanel";
import { OriginalEvidenceViewer } from "../components/evidence-workspace/OriginalEvidenceViewer";
import { SelectiveVisionTaskPanel } from "../components/evidence-workspace/SelectiveVisionTaskPanel";
import { SourceMetadataEditor } from "../components/evidence-workspace/SourceMetadataEditor";
import type {
  CorrectionDraft,
  RiskReviewDraft,
} from "../components/evidence-workspace/OcrReviewPanel";
import type { ReferencedDocumentDraft } from "../components/evidence-workspace/ReferencedDocumentsPanel";
import type {
  CorrectionCreateRequestWire,
  ReferencedDocumentConfirmRequestWire,
  ReferencedDocumentCreateRequestWire,
  ReferencedDocumentDismissRequestWire,
  ReferencedDocumentResolveRequestWire,
  ReferencedDocumentReviseRequestWire,
  RiskReviewCreateRequestWire,
  RiskPageReviewCreateRequestWire,
} from "../api/evidence";
import {
  isProcessingCandidatePending,
  type ProcessingCandidateView,
} from "../api/evidence/evidenceProcessingViewModels";
import { useFactNormalizationJob } from "../features/fact-normalization/useFactNormalizationJob";
import { ProfileNormalizationStatus } from "../components/profile/ProfileNormalizationStatus";

function toActionError(error: unknown): string {
  if (error instanceof EvidenceApiError) return error.message;
  if (error instanceof EvidenceDecodeError) return error.message;
  return UI_PHRASES.temporarilyUnavailable;
}

function processingCandidateNotice(candidate: ProcessingCandidateView): string {
  switch (candidate.candidateStatus) {
    case "staged":
    case "processing":
      return "已保存，正在生成核对后的资料版本";
    case "needs_attention":
      return "已保存，生成核对后的资料版本前需要完成识别核对。";
    case "retryable_failure":
      return "已保存，但核对后的资料版本处理未完成，可稍后重试。";
    case "terminal_failure":
      return "已保存，但核对后的资料版本未能生成，请重新核对后再试。";
    case "ready":
      return "核对后的资料版本已生成，尚未启用。";
    case "active":
      return "核对后的资料版本已生成并已启用。";
    case "revision_conflict":
      return "资料版本发生变化，请刷新后重新核对。";
    case "cancelled":
      return "核对后的资料版本生成已取消，当前有效资料版本未改变。";
  }
}

const PROCESSING_STATUSES = new Set([
  "added",
  "expected_reprocessing",
  "conflict",
]);

const UNFINISHED_SNAPSHOT_STATUSES = new Set([
  "staged",
  "processing",
  "needs_attention",
  "retryable_failure",
  "ready",
  "revision_conflict",
]);

function buildButtonState(candidate: ProcessingCandidateView | null): {
  disabled: boolean;
  label: string;
} {
  if (candidate === null) {
    return { disabled: false, label: "检查核对结果并生成资料版本" };
  }
  switch (candidate.candidateStatus) {
    case "staged":
    case "processing":
      return { disabled: true, label: "正在检查核对结果…" };
    case "needs_attention":
      return { disabled: true, label: "还有内容待核对" };
    case "retryable_failure":
      return { disabled: true, label: "处理未完成，请查看详情" };
    case "ready":
      return { disabled: true, label: "资料版本待启用" };
    case "revision_conflict":
      return { disabled: true, label: "资料已变化，请刷新" };
    case "terminal_failure":
    case "cancelled":
    case "active":
      return { disabled: false, label: "重新检查并生成资料版本" };
  }
}

/** 待处理数量：本次预览中需要处理/需要重新识别的文件数。 */
function pendingCountOf(preview: EvidenceUploadPreviewView | null): number {
  if (preview === null) return 0;
  return preview.items.filter((item) => PROCESSING_STATUSES.has(item.status))
    .length;
}

function formatLocalDate(iso: string): string {
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return iso.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(value);
}

function leftToneOf(
  item: EvidenceItemView,
): "added" | "reuse" | "attention" | "omitted" | "rejected" {
  if (item.status === "added") return "added";
  if (item.status === "duplicate") return "reuse";
  if (item.status === "conflict" || item.status === "expected_reprocessing") {
    return "attention";
  }
  if (item.status === "full_snapshot_omission") return "omitted";
  return "rejected";
}

interface PageDetailResult {
  page: ProcessingRevisionPageView;
  data: OcrPageView | null;
  error: unknown | null;
}

/**
 * 当前资料版本只使用已加载快照列表的活动快照指针（design.md：episode.revision 是
 * 审核节点修订号，不是资料版本）。无任何快照、已有候选但未启用、当前有效是三个不同业务状态，
 * 不得用同一文案混在一起。候选状态和列表顺序不参与当前版本推导。
 */
function currentSnapshotVersionLabel(
  snapshots: UseLoadResult<EvidenceSnapshotListView>,
): string {
  if (snapshots.state.status === "loading") return "正在读取…";
  if (snapshots.state.status === "error") return "暂时无法读取";
  const { activeEvidenceSnapshotId, items } = snapshots.state.data;
  if (items.length === 0) return "尚未建立资料版本";
  if (activeEvidenceSnapshotId === null) return "尚未启用";
  if (
    !items.some((item) => item.evidenceSnapshotId === activeEvidenceSnapshotId)
  ) {
    return "当前版本不可读取";
  }
  return "当前有效";
}

export function canSupplementEvidence(
  activeEvidenceSnapshotId: string | null,
): boolean {
  return activeEvidenceSnapshotId !== null;
}

export function EvidencePage() {
  const { path, params } = useHashRoute();
  const routeParams = matchRouteParams(path, "/subjects/:subjectId/evidence");
  const subjectIdParam = routeParams?.subjectId ?? null;
  const episodeParam = params.get("episode");

  // 上下文：按 URL 中的真实受试者与审核节点直接读取，不经过合成看板。
  const contextReady = subjectIdParam !== null && episodeParam !== null;
  const context = useLoad(
    (signal) =>
      getCatalogRepository().getEvidenceContext(
        subjectIdParam as string,
        episodeParam as string,
        signal,
      ),
    [subjectIdParam, episodeParam],
    { enabled: contextReady },
  );

  // 上传工作流状态
  const [mode, setMode] = useState<EvidenceUploadMode | null>(null);
  const [uploadPanelExpanded, setUploadPanelExpanded] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<EvidenceUploadPreviewView | null>(
    null,
  );
  const [previewBusy, setPreviewBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [resolutions, setResolutions] = useState<
    Record<string, EvidenceConflictResolution>
  >({});
  const [commitResult, setCommitResult] = useState<EvidenceCommitView | null>(
    null,
  );
  const [selectedFileId, setSelectedFileId] = useState<string | null>(null);
  const [metadataBusy, setMetadataBusy] = useState(false);
  const [metadataError, setMetadataError] = useState<string | null>(null);
  const [metadataNotice, setMetadataNotice] = useState<string | null>(null);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(
    null,
  );
  const [snapshotsKey, setSnapshotsKey] = useState(0);
  /** 幂等键随预览生命周期：从首次确认尝试到成功/取消/被替换复用同一键，不显示给用户。 */
  const [idempotencyKey, setIdempotencyKey] = useState<string | null>(null);

  // 派生上下文（数据未就绪时为空；所有 hook 无条件调用）
  const project =
    context.state.status === "success" ? context.state.data.project : null;
  const subject =
    context.state.status === "success" ? context.state.data.subject : undefined;
  const episode =
    context.state.status === "success" ? context.state.data.episode : undefined;
  const subjectId: SubjectId | null =
    subjectIdParam !== null && subject !== undefined
      ? (subjectIdParam as SubjectId)
      : null;
  const reviewEpisodeId =
    episode !== undefined ? episode.reviewEpisodeId : null;
  const baseRevision = episode !== undefined ? episode.revision : 1;
  const scopeReady = subjectId !== null && reviewEpisodeId !== null;

  const factNormalization = useFactNormalizationJob({
    subjectId,
    reviewEpisodeId,
  });

  // 证据快照列表（作用域：当前受试者 × 审核节点）
  const snapshots = useLoad(
    () =>
      getEvidenceRepository().listEvidenceSnapshots(
        subjectId as SubjectId,
        reviewEpisodeId as string,
      ),
    [subjectId, reviewEpisodeId, snapshotsKey],
    { enabled: scopeReady },
  );

  useEffect(() => {
    if (snapshots.state.status !== "success") return;
    if (
      selectedSnapshotId !== null &&
      snapshots.state.data.items.some(
        (item) => item.evidenceSnapshotId === selectedSnapshotId,
      )
    )
      return;
    setSelectedSnapshotId(
      snapshots.state.data.activeEvidenceSnapshotId ??
        snapshots.state.data.items[0]?.evidenceSnapshotId ??
        null,
    );
  }, [selectedSnapshotId, snapshots.state]);

  const selectedSnapshot =
    snapshots.state.status === "success" && selectedSnapshotId !== null
      ? (snapshots.state.data.items.find(
          (item) => item.evidenceSnapshotId === selectedSnapshotId,
        ) ?? null)
      : null;
  const unfinishedSnapshot =
    snapshots.state.status === "success"
      ? (snapshots.state.data.items.find(
          (item) =>
            !item.isCurrent && UNFINISHED_SNAPSHOT_STATUSES.has(item.status),
        ) ?? null)
      : null;
  const unfinishedJobId =
    unfinishedSnapshot?.latestProcessingCandidate?.jobId ??
    unfinishedSnapshot?.uploadJobId ??
    null;

  // 当前有效版本与待启用版本都必须由服务端给出确切修订 ID，页面不按时间猜测。
  const activeProcessingRevisionId =
    snapshots.state.status === "success"
      ? snapshots.state.data.activeEvidenceProcessingRevisionId
      : null;
  const activeSnapshotId =
    snapshots.state.status === "success"
      ? snapshots.state.data.activeEvidenceSnapshotId
      : null;
  const viewedProcessingRevisionId =
    selectedSnapshotId === activeSnapshotId
      ? activeProcessingRevisionId
      : (selectedSnapshot?.baseProcessingRevisionId ?? null);
  const processingRevision = useLoad(
    () =>
      getEvidenceRepository().getProcessingRevision(
        viewedProcessingRevisionId as string,
      ),
    [viewedProcessingRevisionId],
    { enabled: scopeReady && viewedProcessingRevisionId !== null },
  );
  const viewedRevisionConsistent =
    processingRevision.state.status === "success" &&
    processingRevision.state.data.revisionId === viewedProcessingRevisionId &&
    processingRevision.state.data.evidenceSnapshotId === selectedSnapshotId &&
    (selectedSnapshotId !== activeSnapshotId ||
      processingRevision.state.data.isCurrent);
  useEffect(() => {
    if (
      snapshots.state.status !== "success" ||
      selectedSnapshot === null ||
      selectedSnapshot.isCurrent ||
      selectedSnapshot.baseProcessingRevisionId !== null
    )
      return;
    const timer = window.setTimeout(
      () => setSnapshotsKey((key) => key + 1),
      1_000,
    );
    return () => window.clearTimeout(timer);
  }, [selectedSnapshot, snapshots.state]);
  const openablePageEntries = useMemo(
    () =>
      processingRevision.state.status === "success" && viewedRevisionConsistent
        ? processingRevision.state.data.pages.filter(
            (page) => page.ocrPageId !== null,
          )
        : [],
    [viewedRevisionConsistent, processingRevision.state],
  );
  const revisionPageEntries = useMemo(
    () =>
      processingRevision.state.status === "success" && viewedRevisionConsistent
        ? processingRevision.state.data.pages
        : [],
    [viewedRevisionConsistent, processingRevision.state],
  );
  const openablePageKey = openablePageEntries
    .map((page) => `${page.entryId}:${page.ocrPageId ?? ""}`)
    .join("|");
  const [selectedPageEntryId, setSelectedPageEntryId] = useState<string | null>(
    null,
  );
  const [selectedLocatorId, setSelectedLocatorId] = useState<string | null>(
    null,
  );
  const [pageDetailsKey, setPageDetailsKey] = useState(0);
  const [referencedDocumentsKey, setReferencedDocumentsKey] = useState(0);
  const [ocrConflict, setOcrConflict] = useState<EvidenceApiError | null>(null);
  const [referencedConflict, setReferencedConflict] =
    useState<EvidenceApiError | null>(null);
  const [processingActionError, setProcessingActionError] = useState<
    string | null
  >(null);
  const [referencedActionError, setReferencedActionError] = useState<
    string | null
  >(null);
  const [processingNotice, setProcessingNotice] = useState<string | null>(null);
  const [processingCandidate, setProcessingCandidate] =
    useState<ProcessingCandidateView | null>(null);
  const [buildBusy, setBuildBusy] = useState(false);
  const currentCandidateId = useRef<string | null>(null);
  const candidateScope = useRef(
    `${subjectIdParam ?? ""}:${episodeParam ?? ""}`,
  );
  const actionIdempotencyKeys = useRef<Record<string, string>>({});

  useEffect(() => {
    const nextScope = `${subjectIdParam ?? ""}:${episodeParam ?? ""}`;
    if (candidateScope.current === nextScope) return;
    candidateScope.current = nextScope;
    currentCandidateId.current = null;
    setProcessingCandidate(null);
    setProcessingNotice(null);
  }, [episodeParam, subjectIdParam]);

  useEffect(() => {
    if (reviewEpisodeId === null || snapshots.state.status === "success")
      return;
    const storageKey = `evidence-processing-candidate:${reviewEpisodeId}`;
    const storedCandidateId = window.localStorage.getItem(storageKey);
    if (storedCandidateId === null) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let failures = 0;
    const restore = async () => {
      try {
        const candidate = await getEvidenceRepository().getProcessingCandidate(
          storedCandidateId,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (candidate == null) return;
        if (
          window.localStorage.getItem(storageKey) !== storedCandidateId ||
          (currentCandidateId.current !== null &&
            currentCandidateId.current !== storedCandidateId)
        ) {
          return;
        }
        currentCandidateId.current = candidate.candidateId;
        setProcessingActionError(null);
        setProcessingCandidate(candidate);
      } catch (error) {
        if (controller.signal.aborted) return;
        if (error instanceof EvidenceApiError && error.statusCode === 404) {
          if (
            window.localStorage.getItem(storageKey) === storedCandidateId &&
            (currentCandidateId.current === null ||
              currentCandidateId.current === storedCandidateId)
          ) {
            window.localStorage.removeItem(storageKey);
          }
          return;
        }
        setProcessingActionError(toActionError(error));
        failures += 1;
        timer = window.setTimeout(
          () => void restore(),
          Math.min(800 * 2 ** failures, 5_000),
        );
      }
    };
    void restore();
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [reviewEpisodeId, snapshots.state.status, subjectId]);

  useEffect(() => {
    const candidate = selectedSnapshot?.latestProcessingCandidate ?? null;
    if (selectedSnapshot === null || reviewEpisodeId === null) return;
    const storageKey = `evidence-processing-candidate:${reviewEpisodeId}`;
    if (candidate === null) {
      currentCandidateId.current = null;
      window.localStorage.removeItem(storageKey);
      setProcessingCandidate(null);
      setProcessingNotice(null);
      return;
    }
    currentCandidateId.current = candidate.candidateId;
    window.localStorage.setItem(storageKey, candidate.candidateId);
    setProcessingActionError(null);
    setProcessingCandidate(candidate);
    setProcessingNotice(processingCandidateNotice(candidate));
  }, [
    reviewEpisodeId,
    selectedSnapshot?.evidenceSnapshotId,
    selectedSnapshot?.latestProcessingCandidate?.candidateEventSeq,
    selectedSnapshot?.latestProcessingCandidate?.candidateId,
    selectedSnapshot?.latestProcessingCandidate?.candidateStatus,
  ]);

  useEffect(() => {
    if (processingCandidate == null || reviewEpisodeId === null) return;
    const storageKey = `evidence-processing-candidate:${reviewEpisodeId}`;
    window.localStorage.setItem(storageKey, processingCandidate.candidateId);
    if (!isProcessingCandidatePending(processingCandidate.candidateStatus))
      return;
    const controller = new AbortController();
    let timer: number | undefined;
    let failures = 0;
    const poll = async () => {
      try {
        const candidate = await getEvidenceRepository().getProcessingCandidate(
          processingCandidate.candidateId,
          { signal: controller.signal },
        );
        if (controller.signal.aborted) return;
        if (candidate == null) return;
        if (
          currentCandidateId.current !== processingCandidate.candidateId ||
          window.localStorage.getItem(storageKey) !==
            processingCandidate.candidateId
        ) {
          return;
        }
        failures = 0;
        setProcessingActionError(null);
        setProcessingCandidate(candidate);
        setProcessingNotice(processingCandidateNotice(candidate));
        if (isProcessingCandidatePending(candidate.candidateStatus)) {
          timer = window.setTimeout(() => void poll(), 800);
        }
      } catch (error) {
        if (controller.signal.aborted) return;
        setProcessingActionError(toActionError(error));
        failures += 1;
        timer = window.setTimeout(
          () => void poll(),
          Math.min(800 * 2 ** failures, 5_000),
        );
      }
    };
    timer = window.setTimeout(() => void poll(), 800);
    return () => {
      controller.abort();
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [
    processingCandidate?.candidateEventSeq,
    processingCandidate?.candidateId,
    processingCandidate?.candidateStatus,
    reviewEpisodeId,
    selectedSnapshotId,
  ]);

  useEffect(() => {
    if (
      processingCandidate?.candidateStatus !== "needs_attention" ||
      processingCandidate.candidateEventSeq === null
    ) {
      return;
    }
    // 后台在候选状态变为待核对时才会持久化风险项；候选状态和
    // 当前页明细是两个独立读模型，因此必须重新读取页明细才能呈现新风险。
    setPageDetailsKey((key) => key + 1);
  }, [
    processingCandidate?.candidateEventSeq,
    processingCandidate?.candidateId,
    processingCandidate?.candidateStatus,
  ]);

  useEffect(() => {
    if (revisionPageEntries.length === 0) {
      setSelectedPageEntryId(null);
      return;
    }
    if (
      !revisionPageEntries.some((page) => page.entryId === selectedPageEntryId)
    ) {
      setSelectedPageEntryId(
        openablePageEntries[0]?.entryId ??
          revisionPageEntries[0]?.entryId ??
          null,
      );
    }
  }, [
    openablePageKey,
    openablePageEntries,
    revisionPageEntries,
    selectedPageEntryId,
  ]);

  useEffect(() => {
    setOcrConflict(null);
    setSelectedLocatorId(null);
    setProcessingActionError(null);
    if (processingCandidate != null) {
      setProcessingNotice(processingCandidateNotice(processingCandidate));
    }
  }, [processingCandidate, selectedPageEntryId]);

  const selectedPageEntry = useMemo(
    () =>
      revisionPageEntries.find((page) => page.entryId === selectedPageEntryId),
    [revisionPageEntries, selectedPageEntryId],
  );

  const pageDetails = useLoad(
    async (signal) => {
      if (
        processingRevision.state.status !== "success" ||
        viewedProcessingRevisionId === null ||
        selectedPageEntry === undefined ||
        selectedPageEntry.ocrPageId === null
      ) {
        return null as PageDetailResult | null;
      }
      try {
        const data = await getEvidenceRepository().getOcrPage(
          selectedPageEntry.ocrPageId,
          viewedProcessingRevisionId,
          { signal },
        );
        return { page: selectedPageEntry, data, error: null };
      } catch (error) {
        return { page: selectedPageEntry, data: null, error };
      }
    },
    [
      viewedProcessingRevisionId,
      selectedPageEntry?.entryId,
      selectedPageEntry?.ocrPageId,
      pageDetailsKey,
    ],
    {
      enabled:
        scopeReady &&
        processingRevision.state.status === "success" &&
        selectedPageEntry !== undefined &&
        selectedPageEntry.ocrPageId !== null,
    },
  );

  const referencedDocuments = useLoad(
    () =>
      getEvidenceRepository().listReferencedDocuments(
        subjectId as SubjectId,
        reviewEpisodeId as string,
      ),
    [subjectId, reviewEpisodeId, referencedDocumentsKey],
    { enabled: scopeReady },
  );

  function chooseMode(next: EvidenceUploadMode) {
    setMode(next);
    setPreview(null);
    setSelectedFiles([]);
    setResolutions({});
    setCommitResult(null);
    setActionError(null);
    setNotice(null);
    setIdempotencyKey(null);
  }

  async function createPreview(currentMode: EvidenceUploadMode, files: File[]) {
    if (files.length === 0) return;
    setPreviewBusy(true);
    setActionError(null);
    setNotice(null);
    setCommitResult(null);
    setPreview(null);
    try {
      const result = await getEvidenceRepository().createUploadPreview({
        subjectId: subjectId as SubjectId,
        reviewEpisodeId: reviewEpisodeId as string,
        uploadMode: currentMode,
        baseRevision,
        actor: "本地用户",
        files,
      });
      setPreview(result);
      setResolutions({});
      setSelectedFileId(null);
      // 新预览开始新的幂等生命周期
      setIdempotencyKey(crypto.randomUUID());
    } catch (error) {
      setActionError(toActionError(error));
    } finally {
      setPreviewBusy(false);
    }
  }

  function onFilesChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (mode === null || files.length === 0) return;
    setSelectedFiles(files);
    void createPreview(mode, files);
  }

  async function removeItem(itemId: string) {
    if (preview === null || previewBusy) return;
    // 按“预览中非遗漏的上传条目次序”映射所选文件：完整资料遗漏行来自基准快照，
    // 不占本次上传文件的下标。
    const uploadedItems = preview.items.filter(
      (item) => item.status !== "full_snapshot_omission",
    );
    if (uploadedItems.length !== selectedFiles.length) {
      setActionError(
        "所选文件与预览条目不一致，无法移除该文件。请取消预览后重新选择。",
      );
      return;
    }
    const fileIndex = uploadedItems.findIndex((item) => item.itemId === itemId);
    if (fileIndex < 0) return;
    // 必须先成功取消旧预览（清理预览自有暂存）；失败则保留当前预览、显示后端中文
    // 错误，不生成新预览。
    setPreviewBusy(true);
    setActionError(null);
    try {
      await getEvidenceRepository().cancelUploadPreview(preview.previewId);
    } catch (error) {
      setActionError(toActionError(error));
      setPreviewBusy(false);
      return;
    }
    const remaining = selectedFiles.filter(
      (_, itemIndex) => itemIndex !== fileIndex,
    );
    setPreview(null);
    setCommitResult(null);
    if (remaining.length === 0) {
      setSelectedFiles([]);
      setResolutions({});
      setIdempotencyKey(null);
      setNotice("已移除全部所选文件。");
      setPreviewBusy(false);
      return;
    }
    setSelectedFiles(remaining);
    await createPreview(preview.uploadMode, remaining);
  }

  async function cancelPreview() {
    if (preview === null) return;
    setPreviewBusy(true);
    setActionError(null);
    try {
      await getEvidenceRepository().cancelUploadPreview(preview.previewId);
      setNotice(null);
      setPreview(null);
      setSelectedFiles([]);
      setResolutions({});
      setCommitResult(null);
      setMode(null);
      setUploadPanelExpanded(false);
      setIdempotencyKey(null);
    } catch (error) {
      setActionError(toActionError(error));
    } finally {
      setPreviewBusy(false);
    }
  }

  const conflictItems =
    preview === null
      ? []
      : preview.items.filter((item) => item.status === "conflict");
  const conflictsUnresolved = conflictItems.filter(
    (item) => resolutions[item.itemId] === undefined,
  ).length;
  const canConfirm =
    preview !== null &&
    preview.status === "staged" &&
    conflictsUnresolved === 0 &&
    preview.items.some((item) =>
      ["added", "duplicate", "conflict", "expected_reprocessing"].includes(
        item.status,
      ),
    ) &&
    preview.matchingSnapshotId === null &&
    !previewBusy;
  // 左栏：文件与页清单条目（预览条目或确认后快照成员）；hook 无条件调用
  const leftEntries = useMemo(() => {
    const pageCounts = new Map<string, number>();
    if (processingRevision.state.status === "success") {
      for (const page of processingRevision.state.data.pages) {
        pageCounts.set(
          page.sourceDocumentVersionId,
          (pageCounts.get(page.sourceDocumentVersionId) ?? 0) + 1,
        );
      }
    }
    const visibleMembers =
      commitResult?.snapshot.members ?? selectedSnapshot?.members;
    if (visibleMembers !== undefined) {
      return visibleMembers.map((member) => {
        const pageCount = pageCounts.get(member.sourceDocumentVersionId);
        return {
          id: member.memberId,
          fileName: member.fileName,
          meta: `${pageCount === undefined ? "页数整理中" : `${pageCount} 页`} · 第 ${member.versionNumber} 版`,
          statusLabel:
            commitResult === null && selectedSnapshot?.isCurrent
              ? "当前资料"
              : member.originLabel,
          tone: (commitResult === null && selectedSnapshot?.isCurrent
            ? "reuse"
            : member.origin === "added"
              ? "added"
              : member.origin === "replaced"
                ? "attention"
                : "reuse") as "added" | "reuse" | "attention",
        };
      });
    }
    if (preview !== null) {
      return preview.items.map((item) => ({
        id: item.itemId,
        fileName: item.fileName,
        meta: formatByteSize(item.byteSize),
        statusLabel: item.statusLabel,
        tone: leftToneOf(item),
      }));
    }
    return [];
  }, [commitResult, preview, processingRevision.state, selectedSnapshot]);
  const selectedMember =
    selectedSnapshot?.members.find(
      (member) => member.memberId === selectedFileId,
    ) ??
    commitResult?.snapshot.members.find(
      (member) => member.memberId === selectedFileId,
    ) ??
    null;

  async function saveSourceMetadata(values: {
    documentType: string;
    sourceParty: string;
    reason: string;
  }): Promise<void> {
    if (selectedMember === null) return;
    const action = `metadata:${selectedMember.sourceDocumentVersionId}:${selectedMember.metadataHead.revision}`;
    setMetadataBusy(true);
    setMetadataError(null);
    setMetadataNotice(null);
    try {
      await getEvidenceRepository().reviseSourceDocumentMetadata(
        selectedMember.sourceDocumentVersionId,
        {
          document_type: values.documentType.trim(),
          source_party: values.sourceParty.trim(),
          reason: values.reason.trim(),
          expected_metadata_revision: selectedMember.metadataHead.revision,
          idempotency_key: idempotencyKeyFor(action),
          actor: "本地用户",
        },
      );
      completeAction(action);
      setSnapshotsKey((key) => key + 1);
      setMetadataNotice("资料类型与提供方已保存，将纳入下一次生成的资料版本。");
    } catch (error) {
      setMetadataError(toActionError(error));
    } finally {
      setMetadataBusy(false);
    }
  }

  async function confirmUpload() {
    if (preview === null) return;
    if (conflictsUnresolved > 0) {
      setActionError("还有同名文件未选择处置方式，请先完成选择。");
      return;
    }
    if (idempotencyKey === null) {
      setActionError("预览状态不完整，请取消预览后重新选择文件。");
      return;
    }
    setPreviewBusy(true);
    setActionError(null);
    try {
      const resolutionsMap: Record<string, string> = {};
      for (const item of conflictItems) {
        resolutionsMap[item.itemId] = resolutions[item.itemId] as string;
      }
      const result = await getEvidenceRepository().confirmUpload(
        preview.previewId,
        {
          preview_sha256: preview.previewSha256,
          upload_mode: preview.uploadMode,
          base_revision: preview.baseRevision,
          // 复用同一幂等键：响应中断后重试仍是同键回放，服务端不会重复建快照
          idempotency_key: idempotencyKey,
          resolutions: resolutionsMap,
        },
      );
      setCommitResult(result);
      setSelectedSnapshotId(result.snapshot.evidenceSnapshotId);
      setPreview(null);
      setSelectedFileId(null);
      setIdempotencyKey(null);
      setSnapshotsKey((key) => key + 1);
      setNotice(null);
    } catch (error) {
      setActionError(toActionError(error));
    } finally {
      setPreviewBusy(false);
    }
  }

  function idempotencyKeyFor(action: string): string {
    const existing = actionIdempotencyKeys.current[action];
    if (existing !== undefined) return existing;
    const key = crypto.randomUUID();
    actionIdempotencyKeys.current[action] = key;
    return key;
  }

  function completeAction(action: string) {
    delete actionIdempotencyKeys.current[action];
  }

  async function buildReviewableRevision(
    snapshot: EvidenceSnapshotListView["items"][number],
  ) {
    if (episode === undefined || snapshot.baseProcessingRevisionId === null)
      return;
    const action = `build:${snapshot.evidenceSnapshotId}:${snapshot.baseProcessingRevisionId}`;
    setBuildBusy(true);
    setProcessingActionError(null);
    setProcessingNotice("正在生成可启用的资料版本…");
    try {
      const result = await getEvidenceRepository().buildProcessingRevision({
        evidence_snapshot_id: snapshot.evidenceSnapshotId,
        base_processing_revision_id: snapshot.baseProcessingRevisionId,
        expected_revision: episode.revision,
        idempotency_key: idempotencyKeyFor(action),
        actor: "本地用户",
        selected_locator_ids: [],
      });
      completeAction(action);
      currentCandidateId.current = result.candidateId;
      window.localStorage.setItem(
        `evidence-processing-candidate:${episode.reviewEpisodeId}`,
        result.candidateId,
      );
      setProcessingCandidate(result);
      setProcessingNotice(processingCandidateNotice(result));
      setSnapshotsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "ocr");
    } finally {
      setBuildBusy(false);
    }
  }

  async function activateReviewableRevision(): Promise<void> {
    if (
      episode === undefined ||
      subjectId === null ||
      processingCandidate?.candidateStatus !== "ready" ||
      processingCandidate.completeRevisionId === null
    )
      return;
    const completeRevisionId = processingCandidate.completeRevisionId;
    const action = `activate:${completeRevisionId}`;
    setProcessingActionError(null);
    try {
      await getEvidenceRepository().activateProcessingRevision(
        completeRevisionId,
        {
          expected_revision: episode.revision,
          idempotency_key: idempotencyKeyFor(action),
          actor: "本地用户",
          reason: "已完成资料分类与识别结果核对，启用本次资料版本。",
          candidate_id: processingCandidate.candidateId,
          job_id: processingCandidate.jobId,
        },
      );
      completeAction(action);
      window.localStorage.removeItem(
        `evidence-processing-candidate:${episode.reviewEpisodeId}`,
      );
      currentCandidateId.current = null;
      setProcessingCandidate(null);
      setProcessingNotice("资料版本已启用；正在整理个例档案。");
      setSnapshotsKey((key) => key + 1);
      context.retry();
      // 启用成功后自动发起整理；幂等键绑定本次启用修订，重复点击复用同一任务。
      await factNormalization.start(
        `profile-organize:activate:${completeRevisionId}`,
      );
    } catch (error) {
      handleProcessingError(error, "ocr");
    }
  }

  function handleProcessingError(error: unknown, area: "ocr" | "referenced") {
    if (error instanceof EvidenceApiError && error.statusCode === 409) {
      if (area === "ocr") {
        setOcrConflict(error);
        setProcessingActionError(null);
      } else {
        setReferencedConflict(error);
        setReferencedActionError(null);
      }
      return;
    }
    if (area === "ocr") {
      setProcessingActionError(toActionError(error));
    } else {
      setReferencedActionError(toActionError(error));
    }
  }

  async function submitCorrection(
    page: OcrPageView,
    draft: CorrectionDraft,
  ): Promise<void> {
    if (buildBusy) {
      setProcessingNotice("正在生成核对后的资料版本，请稍候完成当前操作。");
      return;
    }
    if (
      processingCandidate != null &&
      (isProcessingCandidatePending(processingCandidate.candidateStatus) ||
        processingCandidate.candidateStatus === "retryable_failure")
    ) {
      setProcessingNotice(processingCandidateNotice(processingCandidate));
      return;
    }
    if (processingRevision.state.status !== "success" || episode === undefined)
      return;
    const action = `correction:${page.ocrPageId}:${draft.textStart}:${draft.textEnd}`;
    const body: CorrectionCreateRequestWire = {
      raw_text_sha256: page.rawTextSha256,
      text_start: draft.textStart,
      text_end: draft.textEnd,
      original_text: draft.originalText,
      corrected_text: draft.correctedText,
      change_kind: draft.changeKind,
      reason: draft.reason,
      base_processing_revision_id:
        processingRevision.state.data.baseProcessingRevisionId ??
        processingRevision.state.data.revisionId,
      expected_revision: episode.revision,
      idempotency_key: idempotencyKeyFor(action),
      actor: "本地用户",
      confirmation: draft.criticalConfirmed
        ? { actor: "本地用户", at: new Date().toISOString() }
        : null,
      affected_scope: [],
      ...(processingCandidate?.candidateStatus === "needs_attention" &&
      processingCandidate.candidateEventSeq !== null
        ? {
            target_candidate_id: processingCandidate.candidateId,
            expected_candidate_event_seq: processingCandidate.candidateEventSeq,
          }
        : {}),
    };
    setOcrConflict(null);
    setProcessingActionError(null);
    setProcessingNotice(null);
    try {
      const result = await getEvidenceRepository().createCorrection(
        page.ocrPageId,
        body,
      );
      completeAction(action);
      currentCandidateId.current = result.candidateId;
      window.localStorage.setItem(
        `evidence-processing-candidate:${reviewEpisodeId}`,
        result.candidateId,
      );
      setProcessingCandidate(result);
      setPageDetailsKey((key) => key + 1);
      setProcessingNotice(processingCandidateNotice(result));
    } catch (error) {
      handleProcessingError(error, "ocr");
      throw error;
    }
  }

  async function submitRiskReview(
    page: OcrPageView,
    flag: OcrRiskFlagView,
    draft: RiskReviewDraft,
  ): Promise<void> {
    if (buildBusy) {
      setProcessingNotice("正在生成核对后的资料版本，请稍候完成当前操作。");
      return;
    }
    if (
      processingCandidate != null &&
      (isProcessingCandidatePending(processingCandidate.candidateStatus) ||
        processingCandidate.candidateStatus === "retryable_failure")
    ) {
      setProcessingNotice(processingCandidateNotice(processingCandidate));
      return;
    }
    if (processingRevision.state.status !== "success" || episode === undefined)
      return;
    const action = `risk:${page.ocrPageId}:${flag.riskFlagId}`;
    const body: RiskReviewCreateRequestWire = {
      risk_flag_id: flag.riskFlagId,
      decision: draft.decision,
      reason: draft.reason,
      base_processing_revision_id:
        processingRevision.state.data.baseProcessingRevisionId ??
        processingRevision.state.data.revisionId,
      expected_revision: episode.revision,
      idempotency_key: idempotencyKeyFor(action),
      actor: "本地用户",
      ...(processingCandidate?.candidateStatus === "needs_attention" &&
      processingCandidate.candidateEventSeq !== null
        ? {
            target_candidate_id: processingCandidate.candidateId,
            expected_candidate_event_seq: processingCandidate.candidateEventSeq,
          }
        : {}),
    };
    setOcrConflict(null);
    setProcessingActionError(null);
    setProcessingNotice(null);
    try {
      const result = await getEvidenceRepository().createRiskReview(
        page.ocrPageId,
        body,
      );
      completeAction(action);
      currentCandidateId.current = result.candidateId;
      window.localStorage.setItem(
        `evidence-processing-candidate:${reviewEpisodeId}`,
        result.candidateId,
      );
      setProcessingCandidate(result);
      setPageDetailsKey((key) => key + 1);
      setProcessingNotice(processingCandidateNotice(result));
    } catch (error) {
      handleProcessingError(error, "ocr");
      throw error;
    }
  }

  async function submitPageRiskReview(
    page: OcrPageView,
    scanId: string,
    reason: string,
  ): Promise<void> {
    if (buildBusy) {
      setProcessingNotice("正在生成核对后的资料版本，请稍候完成当前操作。");
      return;
    }
    if (
      processingCandidate != null &&
      (isProcessingCandidatePending(processingCandidate.candidateStatus) ||
        processingCandidate.candidateStatus === "retryable_failure")
    ) {
      setProcessingNotice(processingCandidateNotice(processingCandidate));
      return;
    }
    if (processingRevision.state.status !== "success" || episode === undefined)
      return;
    const action = `risk-page:${page.ocrPageId}:${scanId}`;
    const body: RiskPageReviewCreateRequestWire = {
      scan_id: scanId,
      decision: "confirmed_as_read",
      reason,
      base_processing_revision_id:
        processingRevision.state.data.baseProcessingRevisionId ??
        processingRevision.state.data.revisionId,
      expected_revision: episode.revision,
      idempotency_key: idempotencyKeyFor(action),
      actor: "本地用户",
      ...(processingCandidate?.candidateStatus === "needs_attention" &&
      processingCandidate.candidateEventSeq !== null
        ? {
            target_candidate_id: processingCandidate.candidateId,
            expected_candidate_event_seq: processingCandidate.candidateEventSeq,
          }
        : {}),
    };
    setOcrConflict(null);
    setProcessingActionError(null);
    setProcessingNotice(null);
    try {
      const result = await getEvidenceRepository().createRiskPageReview(
        page.ocrPageId,
        body,
      );
      completeAction(action);
      currentCandidateId.current = result.candidateId;
      window.localStorage.setItem(
        `evidence-processing-candidate:${reviewEpisodeId}`,
        result.candidateId,
      );
      setProcessingCandidate(result);
      setPageDetailsKey((key) => key + 1);
      setProcessingNotice(processingCandidateNotice(result));
    } catch (error) {
      handleProcessingError(error, "ocr");
      throw error;
    }
  }

  async function createReferencedDocument(
    draft: ReferencedDocumentDraft,
    triggerLocatorId: string | null,
  ): Promise<void> {
    if (episode === undefined) return;
    const action = "referenced:create";
    const body: ReferencedDocumentCreateRequestWire = {
      review_episode_id: episode.reviewEpisodeId,
      expected_revision: episode.revision,
      idempotency_key: idempotencyKeyFor(action),
      description: draft.description,
      document_type: draft.documentType.trim() || null,
      source_party: draft.sourceParty.trim() || null,
      origin: "manual",
      trigger_locator_id: triggerLocatorId,
      actor: "本地用户",
    };
    setReferencedConflict(null);
    setReferencedActionError(null);
    try {
      await getEvidenceRepository().createReferencedDocument(
        subjectId as SubjectId,
        body,
      );
      completeAction(action);
      setReferencedDocumentsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "referenced");
      throw error;
    }
  }

  async function reviseReferencedDocument(
    item: ReferencedDocumentView,
    draft: ReferencedDocumentDraft,
  ): Promise<void> {
    const action = `referenced:revise:${item.referencedDocumentId}`;
    const body: ReferencedDocumentReviseRequestWire = {
      expected_revision: item.revision,
      idempotency_key: idempotencyKeyFor(action),
      description: draft.description,
      document_type: draft.documentType.trim() || null,
      source_party: draft.sourceParty.trim() || null,
      reason: draft.reason,
      actor: "本地用户",
    };
    setReferencedConflict(null);
    setReferencedActionError(null);
    try {
      await getEvidenceRepository().reviseReferencedDocument(
        item.referencedDocumentId,
        body,
      );
      completeAction(action);
      setReferencedDocumentsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "referenced");
      throw error;
    }
  }

  async function confirmReferencedDocument(
    item: ReferencedDocumentView,
    triggerLocatorId: string,
    reason: string,
  ): Promise<void> {
    const action = `referenced:confirm:${item.referencedDocumentId}`;
    const body: ReferencedDocumentConfirmRequestWire = {
      expected_revision: item.revision,
      idempotency_key: idempotencyKeyFor(action),
      trigger_locator_id: triggerLocatorId,
      reason,
      actor: "本地用户",
    };
    setReferencedConflict(null);
    setReferencedActionError(null);
    try {
      await getEvidenceRepository().confirmReferencedDocument(
        item.referencedDocumentId,
        body,
      );
      completeAction(action);
      setReferencedDocumentsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "referenced");
      throw error;
    }
  }

  async function dismissReferencedDocument(
    item: ReferencedDocumentView,
    reason: string,
  ): Promise<void> {
    const action = `referenced:dismiss:${item.referencedDocumentId}`;
    const body: ReferencedDocumentDismissRequestWire = {
      expected_revision: item.revision,
      idempotency_key: idempotencyKeyFor(action),
      reason,
      actor: "本地用户",
    };
    setReferencedConflict(null);
    setReferencedActionError(null);
    try {
      await getEvidenceRepository().dismissReferencedDocument(
        item.referencedDocumentId,
        body,
      );
      completeAction(action);
      setReferencedDocumentsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "referenced");
      throw error;
    }
  }

  async function resolveReferencedDocument(
    item: ReferencedDocumentView,
    sourceDocumentVersionId: string,
  ): Promise<void> {
    const action = `referenced:resolve:${item.referencedDocumentId}`;
    const body: ReferencedDocumentResolveRequestWire = {
      expected_revision: item.resolution?.revision ?? 0,
      idempotency_key: idempotencyKeyFor(action),
      status: "provided",
      source_document_version_id: sourceDocumentVersionId,
      actor: "本地用户",
    };
    setReferencedConflict(null);
    setReferencedActionError(null);
    try {
      await getEvidenceRepository().resolveReferencedDocument(
        item.referencedDocumentId,
        body,
      );
      completeAction(action);
      setReferencedDocumentsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "referenced");
      throw error;
    }
  }

  async function unresolveReferencedDocument(
    item: ReferencedDocumentView,
  ): Promise<void> {
    const action = `referenced:unresolve:${item.referencedDocumentId}`;
    setReferencedConflict(null);
    setReferencedActionError(null);
    try {
      await getEvidenceRepository().unresolveReferencedDocument(
        item.referencedDocumentId,
        item.resolution?.revision ?? 0,
        idempotencyKeyFor(action),
      );
      completeAction(action);
      setReferencedDocumentsKey((key) => key + 1);
    } catch (error) {
      handleProcessingError(error, "referenced");
      throw error;
    }
  }

  if (!contextReady) {
    return (
      <FeedbackBlock
        title="没有指定需要查看的审核节点。"
        hint="请从受试者资料页选择一个审核节点。"
      />
    );
  }
  if (context.state.status === "loading") {
    return <LoadingState />;
  }
  if (context.state.status === "error") {
    return (
      <ErrorState message={context.state.message} onRetry={context.retry} />
    );
  }
  if (subject === undefined || subjectIdParam === null) {
    return (
      <FeedbackBlock
        title="未找到这个受试者。"
        hint="地址中的受试者无效或已不在当前项目中。请从受试者资料页重新选择。"
      />
    );
  }
  if (episode === undefined || episodeParam === null) {
    return (
      <FeedbackBlock
        title={UI_PHRASES.workbenchEpisodeNotFound}
        hint={UI_PHRASES.workbenchEpisodeNotFoundHint}
      />
    );
  }
  if (project === null) {
    return (
      <FeedbackBlock
        title="未找到这个项目。"
        hint="当前项目资料缺失，请从项目看板重新选择后重试。"
      />
    );
  }

  const subjectCode = subject.subjectCode;
  const centerLabel =
    subject.centerCode !== null && subject.centerName !== null
      ? `${subject.centerCode}｜${subject.centerName}`
      : (subject.centerCode ?? subject.centerName ?? "中心信息尚未填写");
  const projectLabel = `${project.projectName} · ${project.studyPhaseLabel}`;
  const pendingCount = pendingCountOf(preview);
  const viewedPairConsistent = viewedRevisionConsistent;
  const viewedMemberByVersionId = new Map(
    (selectedSnapshot?.members ?? []).map((member) => [
      member.sourceDocumentVersionId,
      member,
    ]),
  );
  const selectedPageResult =
    pageDetails.state.status === "success"
      ? (pageDetails.state.data ?? undefined)
      : undefined;
  const actualLocators: LocatorView[] =
    selectedPageResult?.data?.locators ?? [];

  const leftContent = (
    <div className="evidence-files">
      {leftEntries.length > 0 ? (
        <ul className="evidence-files__list" aria-label="文件清单">
          {leftEntries.map((entry) => (
            <li key={entry.id}>
              <button
                type="button"
                className={`evidence-files__row evidence-files__row--${entry.tone}${selectedFileId === entry.id ? " evidence-files__row--selected" : ""}`}
                aria-pressed={selectedFileId === entry.id}
                onClick={() => setSelectedFileId(entry.id)}
              >
                <span className="evidence-files__name" title={entry.fileName}>
                  {entry.fileName}
                </span>
                <span className="evidence-files__meta">{entry.meta}</span>
                <span className="chip">{entry.statusLabel}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState
          message="当前审核节点还没有可显示的文件。"
          hint="选择上方上传方式并选择文件后，这里将显示文件与页清单。"
        />
      )}
      {selectedMember !== null && (
        <SourceMetadataEditor
          member={selectedMember}
          busy={metadataBusy}
          error={metadataError}
          notice={metadataNotice}
          onSave={saveSourceMetadata}
        />
      )}
      <section className="evidence-page-index" aria-label="识别页清单">
        <div className="evidence-panel-heading">
          <div>
            <p className="evidence-kicker">资料页</p>
            <h4>识别页清单</h4>
          </div>
          {processingRevision.state.status === "success" && (
            <span className="section-count">
              {processingRevision.state.data.pages.length}
            </span>
          )}
        </div>
        {snapshots.state.status === "loading" ||
        (viewedProcessingRevisionId !== null &&
          processingRevision.state.status === "loading") ? (
          <p className="evidence-subtle">正在读取识别页清单…</p>
        ) : snapshots.state.status === "error" ? (
          <p className="evidence-subtle">
            资料版本暂时无法读取，页清单不会使用猜测编号。
          </p>
        ) : viewedProcessingRevisionId === null ? (
          <p className="evidence-subtle">当前资料尚未形成可核对的识别版本。</p>
        ) : processingRevision.state.status === "error" ? (
          <div className="evidence-notice evidence-notice--error" role="alert">
            识别结果暂时打不开：{processingRevision.state.message}
            <button
              type="button"
              className="button"
              onClick={processingRevision.retry}
            >
              重试
            </button>
          </div>
        ) : processingRevision.state.status !== "success" ? (
          <p className="evidence-subtle">正在读取识别页清单…</p>
        ) : processingRevision.state.data.pages.length === 0 ? (
          <p className="evidence-subtle">当前识别结果没有可查看的页面。</p>
        ) : (
          <ul className="evidence-page-index__list">
            {processingRevision.state.data.pages.map((page) => (
              <li key={page.entryId}>
                <button
                  type="button"
                  className={`evidence-page-index__row${selectedPageEntryId === page.entryId ? " evidence-page-index__row--selected" : ""}${!page.canOpen ? " evidence-page-index__row--disabled" : ""}`}
                  aria-pressed={selectedPageEntryId === page.entryId}
                  onClick={() => setSelectedPageEntryId(page.entryId)}
                >
                  <span
                    className="evidence-page-index__document"
                    title={
                      viewedMemberByVersionId.get(page.sourceDocumentVersionId)
                        ?.fileName ?? "资料名称暂不可读取"
                    }
                  >
                    {viewedMemberByVersionId.get(page.sourceDocumentVersionId)
                      ?.fileName ?? "资料名称暂不可读取"}
                  </span>
                  <span className="evidence-page-index__number">
                    第 {page.pageNumber} 页
                  </span>
                  <span className="evidence-page-index__meta">
                    {page.statusLabel}
                  </span>
                  {page.failureReason !== null && (
                    <span className="evidence-page-index__reason">
                      {page.failureReason}
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
      <SnapshotListPanel
        snapshots={snapshots}
        selectedSnapshotId={selectedSnapshotId}
        onSelect={setSelectedSnapshotId}
        onBuild={buildReviewableRevision}
        building={
          buildBusy ||
          (processingCandidate != null &&
            isProcessingCandidatePending(processingCandidate.candidateStatus))
        }
      />
    </div>
  );

  const centerContent = (
    <div className="evidence-center-content">
      {processingActionError !== null && (
        <div className="evidence-notice evidence-notice--error" role="alert">
          {processingActionError}
        </div>
      )}
      {processingNotice !== null && (
        <div className="evidence-notice evidence-notice--info" role="status">
          {processingNotice}
          {processingCandidate?.jobId !== null &&
            processingCandidate?.jobId !== undefined && (
              <RouteLink
                to="/tasks"
                params={{
                  job: processingCandidate.jobId,
                  subject: subjectId,
                  episode: reviewEpisodeId,
                }}
                className="button"
                ariaLabel="查看本次资料版本生成详情"
              >
                查看本次生成详情
              </RouteLink>
            )}
        </div>
      )}
      <ProfileNormalizationStatus
        state={factNormalization.state}
        onRetry={() => void factNormalization.retry()}
        onOpenProfile={() => {
          if (subjectId === null || reviewEpisodeId === null) return;
          window.location.hash = `#/subjects?subject=${encodeURIComponent(subjectId)}&episode=${encodeURIComponent(reviewEpisodeId)}`;
        }}
      />
      {factNormalization.completedReview && <RouteLink className="button" to="/tasks" params={{
        job: factNormalization.completedReview.jobId, subject: factNormalization.completedReview.subjectId,
        episode: factNormalization.completedReview.reviewEpisodeId,
      }}>查看最近一次资料识别</RouteLink>}
      {viewedProcessingRevisionId !== null && (
        <SelectiveVisionTaskPanel revisionId={viewedProcessingRevisionId} />
      )}
      {processingCandidate?.candidateStatus === "ready" &&
        processingCandidate.completeRevisionId !== null && (
          <section
            className="evidence-publish evidence-publish--sticky"
            aria-label="启用资料版本"
          >
            <div>
              <strong>核对后的资料版本已生成</strong>
              <p>
                启用后将固定本节点的资料与核对结果，并自动开始整理个例档案；入排规则匹配将在下一阶段开放。
              </p>
            </div>
            <button
              type="button"
              className="button button--primary"
              onClick={() => void activateReviewableRevision()}
            >
              启用这个资料版本
            </button>
          </section>
        )}
      {viewedProcessingRevisionId === null &&
        snapshots.state.status === "success" && (
          <div className="evidence-center-placeholder">
            <p className="evidence-placeholder__title">识别结果尚未就绪</p>
            <p className="evidence-placeholder__body">
              当前资料尚未形成可查看的识别版本。系统不会用推测的页码代替真实处理结果。
            </p>
          </div>
        )}
      {processingRevision.state.status === "loading" &&
        viewedProcessingRevisionId !== null && <LoadingState />}
      {processingRevision.state.status === "error" &&
        viewedProcessingRevisionId !== null && (
          <ErrorState
            message={processingRevision.state.message}
            onRetry={processingRevision.retry}
          />
        )}
      {processingRevision.state.status === "success" &&
        viewedProcessingRevisionId !== null &&
        !viewedPairConsistent && (
          <div className="evidence-notice evidence-notice--error" role="alert">
            当前资料版本与处理版本不一致，系统已停止页核对，避免在错误版本上保存操作。请刷新后重试。
          </div>
        )}
      {processingRevision.state.status === "success" &&
        viewedPairConsistent &&
        revisionPageEntries.length === 0 && (
          <EmptyState
            message="当前识别结果没有可打开的页面。"
            hint="处理失败的页面只显示实际失败原因，不会生成无法打开的入口。"
          />
        )}
      {processingRevision.state.status === "success" &&
        selectedPageEntryId !== null &&
        selectedPageEntry !== undefined &&
        (selectedPageEntry.ocrPageId === null ? (
          <div className="evidence-notice evidence-notice--error" role="status">
            <strong>这一页尚未形成可核对的识别文本。</strong>
            <span>
              {selectedPageEntry.failureReason ?? "请在处理详情中重试这一页。"}
            </span>
          </div>
        ) : pageDetails.state.status === "loading" ? (
          <LoadingState />
        ) : selectedPageResult?.error !== null &&
          selectedPageResult?.error !== undefined ? (
          <ErrorState
            message={toActionError(selectedPageResult.error)}
            onRetry={pageDetails.retry}
          />
        ) : selectedPageResult?.data !== null &&
          selectedPageResult?.data !== undefined ? (
          <OcrReviewPanel
            key={`${processingRevision.state.data.revisionId}:${selectedPageResult.data.ocrPageId}`}
            page={selectedPageResult.data}
            revision={processingRevision.state.data}
            isCurrentRevision={processingRevision.state.data.isCurrent}
            conflict={ocrConflict}
            editingDisabledReason={
              buildBusy ||
              (processingCandidate != null &&
                (isProcessingCandidatePending(
                  processingCandidate.candidateStatus,
                ) ||
                  processingCandidate.candidateStatus === "retryable_failure"))
                ? "当前资料版本尚未生成完成，文字校对和风险核对暂不可操作。"
                : null
            }
            onSubmitCorrection={(draft) => {
              if (selectedPageResult.data === null) return Promise.resolve();
              return submitCorrection(selectedPageResult.data, draft);
            }}
            onSubmitRiskReview={(flag, draft) => {
              if (selectedPageResult.data === null) return Promise.resolve();
              return submitRiskReview(selectedPageResult.data, flag, draft);
            }}
            onSubmitPageRiskReview={(scanId, reason) => {
              if (selectedPageResult.data === null) return Promise.resolve();
              return submitPageRiskReview(
                selectedPageResult.data,
                scanId,
                reason,
              );
            }}
            onOpenLocator={(locator) => {
              setSelectedPageEntryId(selectedPageResult.page.entryId);
              setSelectedLocatorId(locator.locatorId);
            }}
          />
        ) : null)}
      {referencedDocuments.state.status === "error" && (
        <div className="evidence-notice evidence-notice--error" role="alert">
          被提及资料暂时打不开：{referencedDocuments.state.message}
          <button
            type="button"
            className="button"
            onClick={referencedDocuments.retry}
          >
            重试
          </button>
        </div>
      )}
      {referencedActionError !== null && (
        <div className="evidence-notice evidence-notice--error" role="alert">
          {referencedActionError}
        </div>
      )}
      <ReferencedDocumentsPanel
        data={
          referencedDocuments.state.status === "success"
            ? referencedDocuments.state.data
            : null
        }
        currentMembers={selectedSnapshot?.members ?? []}
        locators={actualLocators}
        conflict={referencedConflict}
        onCreate={createReferencedDocument}
        onRevise={reviseReferencedDocument}
        onConfirm={confirmReferencedDocument}
        onDismiss={dismissReferencedDocument}
        onResolve={resolveReferencedDocument}
        onUnresolve={unresolveReferencedDocument}
      />
    </div>
  );

  const rightContent =
    processingRevision.state.status === "success" && viewedPairConsistent ? (
      <OriginalEvidenceViewer
        revisionId={processingRevision.state.data.revisionId}
        pages={revisionPageEntries}
        documentNames={
          new Map(
            [...viewedMemberByVersionId.entries()].map(
              ([versionId, member]) => [versionId, member.fileName],
            ),
          )
        }
        selectedEntryId={selectedPageEntryId}
        selectedLocatorId={selectedLocatorId}
        selectedPageLocators={actualLocators}
        onSelectPage={(entryId) => {
          setSelectedPageEntryId(entryId);
          setSelectedLocatorId(null);
        }}
      />
    ) : (
      <div className="evidence-pages-scroll" aria-label="原始资料查看区">
        <div className="evidence-page-placeholder">
          <p className="evidence-page-placeholder__label">原始资料尚未就绪</p>
          <p className="evidence-page-placeholder__body">
            当前资料版本尚未形成可连续查看的原始页面。
          </p>
        </div>
      </div>
    );

  return (
    <div className="evidence-page">
      <header className="evidence-page__head">
        <h1 className="evidence-page__title">证据工作台</h1>
        <p className="evidence-page__note">
          查看当前审核节点的有效资料、识别文字与原件依据。
        </p>
      </header>
      <ContextBand
        projectLabel={projectLabel}
        protocolVersion={project.officialVersion}
        subjectCode={subjectCode}
        centerLabel={centerLabel}
        nodeLabel={episode.workflowStageLabel ?? episode.stageLabel}
        snapshotVersion={currentSnapshotVersionLabel(snapshots)}
        pendingCount={pendingCount}
        backSubjectId={subjectId as SubjectId}
      />

      <section className="evidence-upload" aria-label="资料上传">
        <div className="evidence-upload__head">
          <h2 className="evidence-upload__title">
            {unfinishedSnapshot !== null
              ? "本次资料进度"
              : activeSnapshotId === null
                ? "建立资料版本"
                : "当前资料"}
          </h2>
          {activeSnapshotId !== null &&
            uploadPanelExpanded &&
            preview === null &&
            commitResult === null && (
              <button
                type="button"
                className="button"
                onClick={() => {
                  setMode(null);
                  setSelectedFiles([]);
                  setNotice(null);
                  setUploadPanelExpanded(false);
                }}
              >
                暂不补充
              </button>
            )}
        </div>
        {snapshots.state.status === "loading" ? (
          <p className="evidence-subtle" role="status">
            正在读取当前资料版本…
          </p>
        ) : snapshots.state.status === "error" ? (
          <div className="evidence-notice evidence-notice--error" role="alert">
            当前资料版本暂时无法读取。
            <button type="button" className="button" onClick={snapshots.retry}>
              重试
            </button>
          </div>
        ) : unfinishedSnapshot !== null &&
          preview === null &&
          commitResult === null ? (
          <div className="evidence-commit" role="status">
            <p className="evidence-commit__message">
              {unfinishedSnapshot.latestProcessingCandidate === null
                ? "本次资料正在整理，关闭页面不会中断。"
                : processingCandidateNotice(
                    unfinishedSnapshot.latestProcessingCandidate,
                  )}
            </p>
            <p className="evidence-commit__detail">
              请先完成本次资料的识别核对和启用，再补充或重建资料，避免同时出现两套待处理内容。
            </p>
            <div className="evidence-commit__actions">
              <RouteLink
                to="/tasks"
                params={{
                  ...(unfinishedJobId !== null ? { job: unfinishedJobId } : {}),
                  subject: subjectId,
                  episode: reviewEpisodeId,
                }}
                className="button button--primary"
                ariaLabel="查看本次资料进度"
              >
                查看处理详情
              </RouteLink>
            </div>
          </div>
        ) : activeSnapshotId !== null &&
          !uploadPanelExpanded &&
          mode === null &&
          preview === null &&
          commitResult === null ? (
          <div className="evidence-commit">
            <p className="evidence-commit__message">
              当前有效资料可在下方查看。
            </p>
            <div className="evidence-commit__actions">
              <button
                type="button"
                className="button button--primary"
                onClick={() => setUploadPanelExpanded(true)}
              >
                补充或重建资料
              </button>
            </div>
          </div>
        ) : (
          <UploadModePicker
            mode={mode}
            onSelect={chooseMode}
            disabled={preview !== null}
            canSupplement={canSupplementEvidence(activeSnapshotId)}
          />
        )}

        {mode !== null && commitResult === null && preview === null && (
          <div className="evidence-picker">
            <label
              htmlFor="evidence-file-input"
              className="button button--primary evidence-picker__label"
            >
              选择文件
            </label>
            <input
              id="evidence-file-input"
              type="file"
              multiple
              className="evidence-picker__input"
              disabled={previewBusy}
              onChange={onFilesChosen}
            />
            <p className="evidence-picker__hint">
              支持 PDF、Word、TXT 与常用图片；压缩包暂不支持。
              {selectedFiles.length > 0 &&
                ` 已选择 ${selectedFiles.length} 份文件。`}
            </p>
          </div>
        )}

        {preview !== null && (
          <PreviewReview
            preview={preview}
            resolutions={resolutions}
            onResolve={(itemId, resolution) =>
              setResolutions((current) => ({
                ...current,
                [itemId]: resolution,
              }))
            }
            onRemove={removeItem}
            onCancel={cancelPreview}
            onConfirm={confirmUpload}
            busy={previewBusy}
            canConfirm={canConfirm}
            notice={notice}
            error={actionError}
          />
        )}

        {commitResult !== null && (
          <div className="evidence-commit" role="status">
            <p className="evidence-commit__message">
              {commitResultMessage(commitResult)}
            </p>
            <p className="evidence-commit__detail">
              {commitResult.snapshot.uploadModeLabel} ·{" "}
              {commitResult.snapshot.statusLabel} · 共{" "}
              {commitResult.snapshot.members.length} 份资料
            </p>
            <div className="evidence-commit__actions">
              {commitResult.jobId !== null && (
                <RouteLink
                  to="/tasks"
                  params={{
                    job: commitResult.jobId,
                    subject: subjectId,
                    episode: reviewEpisodeId,
                  }}
                  className="button button--primary"
                  ariaLabel="查看本次资料整理进度"
                >
                  查看处理详情
                </RouteLink>
              )}
              <button
                type="button"
                className="button"
                onClick={() => {
                  setCommitResult(null);
                  setMode(null);
                  setPreview(null);
                  setSelectedFiles([]);
                  setIdempotencyKey(null);
                  setNotice(null);
                }}
              >
                继续补充资料
              </button>
            </div>
          </div>
        )}

        {actionError !== null && preview === null && commitResult === null && (
          <div className="evidence-notice evidence-notice--error" role="alert">
            {actionError}
          </div>
        )}
        {notice !== null && preview === null && (
          <div className="evidence-notice evidence-notice--info" role="status">
            {notice}
          </div>
        )}
      </section>

      <EvidenceWorkspace
        leftTitle="文件与页清单"
        leftContent={leftContent}
        centerTitle="识别文本 / 风险核对"
        centerContent={centerContent}
        rightTitle="原文件页图"
        rightContent={rightContent}
      />
    </div>
  );
}

function SnapshotListPanel({
  snapshots,
  selectedSnapshotId,
  onSelect,
  onBuild,
  building,
}: {
  snapshots: UseLoadResult<EvidenceSnapshotListView>;
  selectedSnapshotId: string | null;
  onSelect: (snapshotId: string) => void;
  onBuild: (
    snapshot: EvidenceSnapshotListView["items"][number],
  ) => Promise<void>;
  building: boolean;
}) {
  if (snapshots.state.status === "loading") {
    return <p className="evidence-pages-hint">正在读取资料版本…</p>;
  }
  if (snapshots.state.status === "error") {
    return (
      <div className="evidence-notice evidence-notice--error" role="alert">
        资料版本暂时打不开：{snapshots.state.message}
        <button type="button" className="button" onClick={snapshots.retry}>
          重试
        </button>
      </div>
    );
  }
  const items = snapshots.state.data.items;
  if (items.length === 0) {
    return <p className="evidence-pages-hint">该审核节点还没有资料版本。</p>;
  }
  return (
    <section className="evidence-snapshots" aria-label="资料版本">
      <h4 className="evidence-snapshots__title">
        资料版本
        <span className="section-count">{items.length}</span>
      </h4>
      <ul className="evidence-snapshots__list">
        {items.map((snapshot) => {
          const buttonState = buildButtonState(
            snapshot.latestProcessingCandidate,
          );
          return (
            <li
              key={snapshot.evidenceSnapshotId}
              className={`evidence-snapshots__row${selectedSnapshotId === snapshot.evidenceSnapshotId ? " evidence-snapshots__row--selected" : ""}`}
            >
              <button
                type="button"
                className="evidence-snapshots__select"
                aria-pressed={
                  selectedSnapshotId === snapshot.evidenceSnapshotId
                }
                onClick={() => onSelect(snapshot.evidenceSnapshotId)}
              >
                <span className="chip">
                  {snapshot.isCurrent
                    ? "当前有效"
                    : snapshot.status === "active"
                      ? "历史资料"
                      : snapshot.baseProcessingRevisionId !== null &&
                          ["staged", "processing"].includes(snapshot.status)
                        ? "待识别核对"
                        : snapshot.statusLabel}
                </span>
                <span className="evidence-snapshots__meta">
                  {snapshot.uploadModeLabel} · {snapshot.members.length} 份资料
                  ·{formatLocalDate(snapshot.createdAt)}
                </span>
              </button>
              {!snapshot.isCurrent &&
                snapshot.baseProcessingRevisionId !== null && (
                  <button
                    type="button"
                    className="button evidence-snapshots__action"
                    disabled={building || buttonState.disabled}
                    onClick={() => void onBuild(snapshot)}
                  >
                    {building ? "正在检查核对结果…" : buttonState.label}
                  </button>
                )}
              {!snapshot.isCurrent &&
                snapshot.baseProcessingRevisionId === null && (
                  <span className="evidence-snapshots__waiting">
                    正在整理资料…
                  </span>
                )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function FeedbackBlock({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="feedback feedback--empty" role="status">
      <p className="feedback__title">{title}</p>
      <p className="feedback__hint">{hint}</p>
    </div>
  );
}

export default EvidencePage;
