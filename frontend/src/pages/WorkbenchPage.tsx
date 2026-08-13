/**
 * 入排工作台（合同 §3.1/§5.2）：规则树、判断/行动/差异、识别文字与原始证据三区协同。
 * - 桌面（容器 ≥1080px）三列并排；窄屏切换“规则 / 判断 / 证据”标签，选择跨切换保留。
 * - 选择由 URL 持有（episode/component/evidence），可分享、可刷新恢复（spec: state-management）。
 * - 证据直达：/workbench?episode=<episode>&component=<component>&evidence=<span> 自动定位。
 */

import { useEffect, useMemo, useState } from "react";
import { getDefaultRepository } from "../api";
import { readLastWorkbenchEpisode, writeLastWorkbenchEpisode } from "../app/lastWorkbenchEpisode";
import { RouteLink, updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { RuleTree } from "../components/review/RuleTree";
import { JudgmentPane } from "../components/review/JudgmentPane";
import { EvidencePane } from "../components/review/EvidencePane";
import { MainStatusBadge } from "../components/shell/StatusBadge";
import { OpenIcon } from "../components/shell/icons";
import { UI_PHRASES } from "../domain/labels";
import type { RuleComponentId, ReviewEpisodeId } from "../domain/ids";
import type { EpisodeSummaryView } from "../domain/viewModels";

type WorkbenchTab = "rules" | "judgment" | "evidence";

export function WorkbenchPage() {
  const { params } = useHashRoute();
  const episodeParam = params.get("episode");
  const componentParam = params.get("component");
  const evidenceParam = params.get("evidence");

  const board = useLoad(() => getDefaultRepository().getBoard(), []);
  const diffs = useLoad(() => getDefaultRepository().getReviewDiffs(), []);

  /**
   * URL 中的审核节点：
   * - 显式指定但无效 → null（渲染明确未找到状态，绝不静默回落到其他受试者）；
   * - 未指定（裸导航）→ 恢复最近一次有效审核节点；无记录时才回落到首个节点。
   */
  const episodeId: ReviewEpisodeId | null = useMemo(() => {
    if (board.state.status !== "success") return null;
    const episodes = board.state.data.episodes;
    const hasEpisode = (id: string | null): id is ReviewEpisodeId =>
      id !== null && episodes.some((episode) => episode.episodeId === id);
    if (episodeParam !== null) {
      return hasEpisode(episodeParam) ? episodeParam : null;
    }
    const last = readLastWorkbenchEpisode();
    if (hasEpisode(last)) return last;
    return (
      [...episodes].sort(
        (a, b) =>
          a.sortRank - b.sortRank ||
          a.subjectCode.localeCompare(b.subjectCode, "zh"),
      )[0]?.episodeId ?? null
    );
  }, [board.state, episodeParam]);

  /** 记录最近一次有效审核节点：无效 URL 不覆盖，避免裸导航误跳其他受试者 */
  useEffect(() => {
    if (episodeId !== null) writeLastWorkbenchEpisode(episodeId);
  }, [episodeId]);

  /** URL 显式指定了审核节点但无效 */
  const invalidEpisode = episodeParam !== null && episodeId === null;

  const episode: EpisodeSummaryView | null = useMemo(() => {
    if (board.state.status !== "success" || episodeId === null) return null;
    return (
      board.state.data.episodes.find((candidate) => candidate.episodeId === episodeId) ??
      null
    );
  }, [board.state, episodeId]);

  const detail = useLoad(
    () =>
      episode === null
        ? Promise.reject(new Error("no episode"))
        : getDefaultRepository().getEpisodeDetail(
            episode.subjectId,
            episode.stage,
          ),
    [episode?.subjectId, episode?.stage],
  );

  /** 窄屏标签（本地显示状态）；直达证据时默认进入证据标签 */
  const [tab, setTab] = useState<WorkbenchTab>(
    evidenceParam !== null ? "evidence" : "rules",
  );
  useEffect(() => {
    if (evidenceParam !== null) setTab("evidence");
  }, [evidenceParam]);

  if (board.state.status === "loading" || diffs.state.status === "loading") {
    return <LoadingState />;
  }
  if (board.state.status === "error") {
    return <ErrorState message={board.state.message} onRetry={board.retry} />;
  }
  if (diffs.state.status === "error") {
    return <ErrorState message={diffs.state.message} onRetry={diffs.retry} />;
  }

  if (invalidEpisode) {
    return (
      <div className="workbench">
        <header className="page-head">
          <h1 className="page-head__title">入排工作台</h1>
        </header>
        <EmptyState
          message={UI_PHRASES.workbenchEpisodeNotFound}
          hint={UI_PHRASES.workbenchEpisodeNotFoundHint}
        />
        <p className="workbench-notfound-action">
          <RouteLink to="/board" className="button button--primary">
            返回项目看板
          </RouteLink>
        </p>
      </div>
    );
  }

  if (episodeId === null || episode === null) {
    return (
      <div className="workbench">
        <header className="page-head">
          <h1 className="page-head__title">入排工作台</h1>
        </header>
        <EmptyState
          message="当前没有可打开的审核节点。"
          hint="请先到项目看板选择一位受试者与审核节点。"
        />
      </div>
    );
  }

  if (detail.state.status === "loading") {
    return <LoadingState />;
  }
  if (detail.state.status === "error") {
    return (
      <div className="workbench">
        <header className="page-head">
          <h1 className="page-head__title">入排工作台</h1>
        </header>
        <ErrorState message={detail.state.message} onRetry={detail.retry} />
      </div>
    );
  }

  const episodeData = detail.state.data;

  /** 选中组件：直达证据时优先选择引用该证据的子项；否则 URL 优先；再回退到第一个子项 */
  const allComponents = episodeData.rules.flatMap((rule) => rule.components);
  let selectedComponent: typeof allComponents[number] | null = null;
  if (evidenceParam !== null) {
    selectedComponent =
      allComponents.find((component) =>
        component.evidence.some((locator) => locator.spanId === evidenceParam),
      ) ?? null;
  }
  if (selectedComponent === null && componentParam !== null) {
    selectedComponent =
      allComponents.find(
        (component) => component.componentId === componentParam,
      ) ?? null;
  }
  if (selectedComponent === null) {
    selectedComponent =
      allComponents.find(
        (component) => component.componentId === episode.focusComponentId,
      ) ??
      allComponents[0] ??
      null;
  }

  const selectComponent = (componentId: RuleComponentId) => {
    updateParams({ component: componentId, evidence: null });
  };

  const diffItems =
    diffs.state.status === "success"
      ? diffs.state.data
          .flatMap((diff) => diff.diffs)
          .filter((item) => item.componentId === selectedComponent?.componentId)
          .map((item) => ({
            priorLabel: item.priorLabel,
            currentLabel: item.currentLabel,
          }))
      : [];

  const sourceDocuments = episodeData.sourceDocuments.map((document) => ({
    documentVersionId: document.documentVersionId,
    fileName: document.fileName,
    documentType: document.documentType,
    sourceParty: document.sourceParty,
    snapshotVersion: document.snapshotVersion,
  }));

  const tabs: ReadonlyArray<{ id: WorkbenchTab; label: string }> = [
    { id: "rules", label: "规则" },
    { id: "judgment", label: "判断" },
    { id: "evidence", label: "证据" },
  ];

  return (
    <div className="workbench">
      <header className="page-head">
        <h1 className="page-head__title">入排工作台</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：展示合成示例数据。{episodeData.subject.subjectCode} ·{" "}
          {episodeData.episode.stageLabel} · 方案 {episodeData.project.protocolVersion} ·
          资料快照第 {episodeData.episode.revision} 版
        </p>
      </header>

      <div className="workbench-episode">
        <span className="workbench-episode__subject">
          {episodeData.subject.subjectCode}
        </span>
        <span className="workbench-episode__stage">{episodeData.episode.stageLabel}</span>
        <MainStatusBadge status={episodeData.episode.mainStatus} />
        <RouteLink
          to="/subjects"
          params={{ subject: episodeData.subject.subjectId, stage: episodeData.episode.stage }}
          className="button button--quiet"
          ariaLabel={`打开 ${episodeData.subject.subjectCode} 的资料页`}
        >
          <OpenIcon size={13} />
          查看资料页
        </RouteLink>
      </div>

      <div className="workbench-tabs" role="tablist" aria-label="工作区切换">
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            id={`workbench-tab-${item.id}`}
            aria-selected={tab === item.id}
            aria-controls={`workbench-panel-${item.id}`}
            className={`workbench-tabs__tab${tab === item.id ? " workbench-tabs__tab--active" : ""}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div className="workbench-panes">
        <div
          id="workbench-panel-rules"
          role="tabpanel"
          aria-labelledby="workbench-tab-rules"
          tabIndex={0}
          className={`workbench-col workbench-col--rules${tab === "rules" ? " workbench-col--visible" : ""}`}
        >
          <div className="workbench-pane workbench-pane--tree" tabIndex={0}>
            <header className="workbench-pane__head">
              <h2 className="workbench-pane__title">规则与判断状态</h2>
            </header>
            <RuleTree
              rules={episodeData.rules}
              selectedComponentId={selectedComponent?.componentId ?? null}
              onSelectComponent={selectComponent}
            />
          </div>
        </div>
        <div
          id="workbench-panel-judgment"
          role="tabpanel"
          aria-labelledby="workbench-tab-judgment"
          className={`workbench-col workbench-col--judgment${tab === "judgment" ? " workbench-col--visible" : ""}`}
        >
          <JudgmentPane
            component={selectedComponent}
            decision={selectedComponent?.decision ?? null}
            diffItems={diffItems}
          />
        </div>
        <div
          id="workbench-panel-evidence"
          role="tabpanel"
          aria-labelledby="workbench-tab-evidence"
          className={`workbench-col workbench-col--evidence${tab === "evidence" ? " workbench-col--visible" : ""}`}
        >
          <EvidencePane
            component={selectedComponent}
            expectations={episodeData.expectations}
            conflicts={episodeData.conflicts}
            sourceDocuments={sourceDocuments}
            focusSpanId={evidenceParam}
          />
        </div>
      </div>
    </div>
  );
}

export default WorkbenchPage;
