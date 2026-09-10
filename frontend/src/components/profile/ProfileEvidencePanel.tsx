/**
 * Patient Profile 证据面板（Slice 5.6，worker_03）：宽屏下与 Phase 4 原件查看器联动。
 * - 用 profile.evidenceNavigation 的完整处理修订加载连续原件页与文档名；
 * - 只把真实 bbox 定位传给 OriginalEvidenceViewer 画唯一单框（非 bbox 不合成坐标）；
 * - 定位详情（ProfileLocatorList）与原件滚动联动：选择定位后滚动到对应页并画框；
 * - 生成中/失败/陈旧档案由页面层处理，本面板只处理证据加载自身状态。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { getEvidenceRepository } from "../../api/evidence";
import type {
  LocatorView,
  ProcessingRevisionPageView,
} from "../../api/evidence";
import type { ProfileItemView } from "../../api/patient-profile";
import { OriginalEvidenceViewer } from "../evidence-workspace/OriginalEvidenceViewer";
import type { PatientProfileModel } from "../../features/patient-profile/model";
import { locatorsForItem } from "../../features/patient-profile/model";
import { useLoad } from "../../app/useLoad";
import { LoadingState, ErrorState } from "../shell/Feedback";
import { ProfileLocatorList, isRealBboxLocator } from "./ProfileLocatorList";

export interface ProfileEvidencePanelProps {
  model: PatientProfileModel;
  item: ProfileItemView;
  onClose: () => void;
  /** 可选的初始页：书面判断候选跳入时优先打开该原件页。 */
  initialPageArtifactId?: string | null;
}

/** 页面定位：pageArtifactId -> 处理修订页 entryId。 */
function pageEntryByArtifact(
  pages: ProcessingRevisionPageView[],
): Map<string, string> {
  const map = new Map<string, string>();
  for (const page of pages) {
    map.set(page.pageArtifactId, page.entryId);
  }
  return map;
}

function locatorMatchesPage(
  locator: LocatorView,
  pages: ReadonlyMap<string, ProcessingRevisionPageView>,
): boolean {
  const page = pages.get(locator.pageArtifactId);
  return page !== undefined &&
    page.pageNumber === locator.pageNumber &&
    page.sourceDocumentVersionId === locator.sourceDocumentVersionId;
}

export function ProfileEvidencePanel({
  model,
  item,
  onClose,
  initialPageArtifactId = null,
}: ProfileEvidencePanelProps) {
  const navigation = model.evidenceNavigation;

  const revision = useLoad(
    (signal) =>
      getEvidenceRepository().getProcessingRevision(
        navigation.completeProcessingRevisionId,
        { signal },
      ),
    [navigation.completeProcessingRevisionId],
  );

  const snapshot = useLoad(
    (signal) =>
      getEvidenceRepository().getEvidenceSnapshot(
        navigation.evidenceSnapshotV2Id,
        { signal },
      ),
    [navigation.evidenceSnapshotV2Id],
  );

  const itemLocators = useMemo(
    () => locatorsForItem(model, item),
    [model, item],
  );

  const pages =
    revision.state.status === "success" ? revision.state.data.pages : [];
  const entryByArtifact = useMemo(
    () => pageEntryByArtifact(pages),
    [pages],
  );
  const pageByArtifact = useMemo(
    () => new Map(pages.map((page) => [page.pageArtifactId, page])),
    [pages],
  );
  const consistentItemLocators = useMemo(
    () => itemLocators.filter((locator) => locatorMatchesPage(locator, pageByArtifact)),
    [itemLocators, pageByArtifact],
  );
  const consistentEvidenceLocators = useMemo(
    () => model.evidenceLocators.filter((locator) => locatorMatchesPage(locator, pageByArtifact)),
    [model.evidenceLocators, pageByArtifact],
  );
  const hasInconsistentLocator = consistentItemLocators.length !== itemLocators.length;

  const documentNames = useMemo(() => {
    if (snapshot.state.status !== "success") return new Map<string, string>();
    return new Map(
      snapshot.state.data.members.map((member) => [
        member.sourceDocumentVersionId,
        member.fileName,
      ]),
    );
  }, [snapshot.state]);

  const [selectedLocatorId, setSelectedLocatorId] = useState<string | null>(
    null,
  );
  const [selectedEntryId, setSelectedEntryId] = useState<string | null>(null);

  // 条目或原件页变化时初始化到候选指定页；没有指定页时选最精确定位。
  useEffect(() => {
    if (initialPageArtifactId !== null) {
      const initialEntryId = entryByArtifact.get(initialPageArtifactId);
      if (initialEntryId !== undefined) {
        const initialLocator =
          consistentItemLocators.find(
            (locator) => locator.pageArtifactId === initialPageArtifactId,
          ) ?? null;
        setSelectedLocatorId(initialLocator?.locatorId ?? null);
        setSelectedEntryId(initialEntryId);
        return;
      }
    }
    const firstReal =
      consistentItemLocators.find((locator) => isRealBboxLocator(locator)) ??
      consistentItemLocators[0] ??
      null;
    if (firstReal === null) {
      setSelectedLocatorId(null);
      setSelectedEntryId(null);
      return;
    }
    setSelectedLocatorId(firstReal.locatorId);
    setSelectedEntryId(
      entryByArtifact.get(firstReal.pageArtifactId) ?? null,
    );
  }, [
    item.itemId,
    consistentItemLocators,
    entryByArtifact,
    initialPageArtifactId,
  ]);

  const selectedPageLocators: LocatorView[] = useMemo(() => {
    if (selectedEntryId === null) return [];
    const artifactId = [...entryByArtifact.entries()].find(
      ([, entryId]) => entryId === selectedEntryId,
    )?.[0];
    if (artifactId === undefined) return [];
    return consistentEvidenceLocators.filter(
      (locator) => locator.pageArtifactId === artifactId,
    );
  }, [consistentEvidenceLocators, selectedEntryId, entryByArtifact]);

  const selectLocator = useCallback(
    (locatorId: string) => {
      const locator = consistentItemLocators.find(
        (candidate) => candidate.locatorId === locatorId,
      );
      if (locator === undefined) return;
      setSelectedLocatorId(locatorId);
      setSelectedEntryId(
        entryByArtifact.get(locator.pageArtifactId) ?? null,
      );
    },
    [consistentItemLocators, entryByArtifact],
  );

  const handleSelectPage = useCallback(
    (entryId: string) => {
      setSelectedEntryId(entryId);
      // 滚动到其它页后保持当前定位选择，但画框仍以真实 bbox + 所在页为准。
    },
    [],
  );

  return (
    <aside
      className="profile-evidence"
      aria-label="该条目的原文证据与定位"
    >
      <header className="profile-evidence__head">
        <div className="profile-evidence__title">
          <h3>{item.title}</h3>
          <p>
            {item.kindLabel} · {item.laneLabel}
          </p>
        </div>
        <button
          type="button"
          className="button profile-evidence__close"
          onClick={onClose}
          aria-label="关闭原文证据"
        >
          关闭
        </button>
      </header>

      {revision.state.status === "loading" ||
      snapshot.state.status === "loading" ? (
        <LoadingState />
      ) : revision.state.status === "error" ? (
        <ErrorState message={revision.state.message} onRetry={revision.retry} />
      ) : snapshot.state.status === "error" ? (
        <ErrorState message={snapshot.state.message} onRetry={snapshot.retry} />
      ) : pages.length === 0 ? (
        <div className="profile-evidence__empty">
          <p>当前档案还没有可连续查看的原始页面。</p>
        </div>
      ) : (
        <div className="profile-evidence__body">
          <div className="profile-evidence__rail">
            <h4 className="profile-evidence__rail-title">定位详情</h4>
            {hasInconsistentLocator && (
              <p className="profile-correction-warning" role="alert">
                档案中的原文定位与实际页面不一致，已停止精确定位。请重新生成病历档案后再核对原文。
              </p>
            )}
            <ProfileLocatorList
              item={item}
              locators={consistentItemLocators}
              selectedLocatorId={selectedLocatorId}
              onSelectLocator={selectLocator}
            />
          </div>
          <div className="profile-evidence__viewer">
            <OriginalEvidenceViewer
              revisionId={navigation.completeProcessingRevisionId}
              pages={pages}
              documentNames={documentNames}
              selectedEntryId={selectedEntryId}
              selectedLocatorId={selectedLocatorId}
              selectedPageLocators={selectedPageLocators}
              onSelectPage={handleSelectPage}
              unavailableRecoveryHint="请关闭原文面板，点击档案上方“查看/补充资料”，在处理详情中重新处理这一页。"
            />
          </div>
        </div>
      )}
    </aside>
  );
}
