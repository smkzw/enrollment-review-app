/**
 * 行动中心（合同 §3.1/§9）：责任方、原因、需补内容、可关闭证据、到期节点与阻断程度。
 * - 溯源待办与阻断缺口分开显示；后续节点尚未到期不作为当前缺口。
 * - 人工确认试用：理由必填，确认后展示状态转移与前后差异，明确不写入资料库。
 * - URL 契约：/actions?action=<ActionId> 直达行动详情。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { getDefaultRepository } from "../api";
import { updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { useSessionState } from "../app/useSessionState";
import { UAT_KEY_MANUAL_ACTIONS } from "../app/uatTrialState";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { BlockingBadge } from "../components/shell/StatusBadge";
import { OpenIcon } from "../components/shell/icons";
import { isProvenanceAction } from "../domain/counts";
import { UI_PHRASES } from "../domain/labels";
import type { ActionId } from "../domain/ids";
import type { ActionState } from "../domain/enums";

type StateFilter = "all" | ActionState;

/** 独立行动类别筛选：溯源提醒保持独立，不并入阻断或笼统关注（I1）。 */
type CategoryFilter = "all" | "provenance";

interface ManualActionRecord {
  actionId: ActionId;
  transition: "closed" | "reopened";
  reason: string;
  at: string;
  operator: string;
  reviewLabel: string;
}

function parseManualActionRecords(value: unknown): ReadonlyArray<ManualActionRecord> | null {
  if (!Array.isArray(value)) return null;
  const records: ManualActionRecord[] = [];
  for (const item of value) {
    if (typeof item !== "object" || item === null) return null;
    const candidate = item as Record<string, unknown>;
    if (
      typeof candidate.actionId !== "string" ||
      (candidate.transition !== "closed" && candidate.transition !== "reopened") ||
      typeof candidate.reason !== "string" ||
      typeof candidate.at !== "string" ||
      typeof candidate.operator !== "string" ||
      typeof candidate.reviewLabel !== "string"
    ) {
      return null;
    }
    records.push({
      actionId: candidate.actionId as ActionId,
      transition: candidate.transition,
      reason: candidate.reason,
      at: candidate.at,
      operator: candidate.operator,
      reviewLabel: candidate.reviewLabel,
    });
  }
  return records;
}

const STATE_FILTERS: ReadonlyArray<{ key: StateFilter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "open", label: "待处理" },
  { key: "closed_manual", label: "已人工确认关闭" },
  { key: "closed_system", label: "已由系统关闭" },
  { key: "reopened", label: "已重新打开" },
  { key: "superseded", label: "已被新资料取代" },
];

const BLOCKING_FILTERS: ReadonlyArray<{ key: "all" | "blocking" | "attention"; label: string }> = [
  { key: "all", label: "全部程度" },
  { key: "blocking", label: "阻断当前节点" },
  { key: "attention", label: "不阻断，需关注" },
];

const CATEGORY_FILTERS: ReadonlyArray<{ key: CategoryFilter; label: string }> = [
  { key: "all", label: "全部类别" },
  { key: "provenance", label: UI_PHRASES.provenanceFilterLabel },
];

export function ActionsPage() {
  const { params } = useHashRoute();
  const actionParam = params.get("action");

  const actions = useLoad(() => getDefaultRepository().getActions(), []);
  const board = useLoad(() => getDefaultRepository().getBoard(), []);

  // 派生选择（非 hook）：数据未就绪时为空
  const allActions =
    actions.state.status === "success" ? actions.state.data : [];
  const urlAction =
    actionParam !== null
      ? allActions.find((action) => action.actionId === actionParam) ?? null
      : null;

  const [stateFilter, setStateFilter] = useState<StateFilter>("all");
  const [blockingFilter, setBlockingFilter] = useState<"all" | "blocking" | "attention">("all");
  const [categoryFilter, setCategoryFilter] = useState<CategoryFilter>("all");

  const sortedActions = [...allActions].sort(
    (a, b) =>
      (a.blockingLevel === "blocking" ? 0 : 1) - (b.blockingLevel === "blocking" ? 0 : 1) ||
      a.subjectCode.localeCompare(b.subjectCode, "zh") ||
      a.dueStageLabel.localeCompare(b.dueStageLabel, "zh"),
  );

  const filtered = sortedActions.filter((action) => {
    if (stateFilter !== "all" && action.state !== stateFilter) return false;
    if (blockingFilter !== "all" && action.blockingLevel !== blockingFilter) {
      return false;
    }
    if (categoryFilter === "provenance" && !isProvenanceAction(action)) {
      return false;
    }
    return true;
  });

  /** 默认选中当前筛选下第一项，使用户立即看到为什么/谁/补什么/可关闭证据 */
  const selectedAction = urlAction ?? filtered[0] ?? null;
  const selectedEpisode =
    selectedAction !== null && board.state.status === "success"
      ? board.state.data.episodes.find(
          (episode) => episode.episodeId === selectedAction.episodeId,
        ) ?? null
      : null;

  const detail = useLoad(
    () =>
      selectedAction === null || selectedEpisode === null
        ? Promise.reject(new Error("no selection"))
        : getDefaultRepository().getEpisodeDetail(
            selectedEpisode.subjectId,
            selectedEpisode.stage,
          ),
    [selectedAction?.actionId, selectedEpisode?.subjectId, selectedEpisode?.stage],
  );

  // 仅保存本次浏览器会话中的操作记录；临床事实仍来自仓储。
  const [manualRecords, setManualRecords, resetManualRecords] = useSessionState<
    ReadonlyArray<ManualActionRecord>
  >(UAT_KEY_MANUAL_ACTIONS, [], parseManualActionRecords);
  const [draftReason, setDraftReason] = useState("");
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const confirmTriggerRef = useRef<HTMLButtonElement>(null);
  const confirmBackRef = useRef<HTMLButtonElement>(null);

  const closeConfirmation = useCallback(() => {
    setShowConfirmation(false);
    requestAnimationFrame(() => confirmTriggerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!showConfirmation) return;
    confirmBackRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeConfirmation();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeConfirmation, showConfirmation]);

  if (actions.state.status === "loading" || board.state.status === "loading") {
    return <LoadingState />;
  }
  if (actions.state.status === "error") {
    return <ErrorState message={actions.state.message} onRetry={actions.retry} />;
  }
  if (board.state.status === "error") {
    return <ErrorState message={board.state.message} onRetry={board.retry} />;
  }

  const componentDecision =
    selectedAction === null || detail.state.status !== "success"
      ? null
      : (() => {
          for (const rule of detail.state.data.rules) {
            const found = rule.components.find(
              (component) =>
                component.componentId === selectedAction.ruleComponentId,
            );
            if (found !== undefined) return found.decision;
          }
          return null;
        })();

  const reviewConfirmation = () => {
    if (selectedAction === null) return;
    const reason = draftReason.trim();
    if (reason === "") {
      setConfirmError("请填写确认理由后再确认关闭。");
      return;
    }
    setConfirmError(null);
    setShowConfirmation(true);
  };

  const confirmAction = () => {
    if (selectedAction === null) return;
    const reason = draftReason.trim();
    const nextIndex = manualRecords.length + 1;
    setManualRecords((current) => [
      ...current,
      {
        actionId: selectedAction.actionId,
        transition: "closed",
        reason,
        at: new Date().toLocaleString("zh-CN", { hour12: false }),
        operator: "本机用户",
        reviewLabel: `第 ${nextIndex} 次重新核对`,
      },
    ]);
    setDraftReason("");
    setShowConfirmation(false);
  };

  const reopenAction = () => {
    if (selectedAction === null) return;
    const nextIndex = manualRecords.length + 1;
    setManualRecords((current) => [
      ...current,
      {
        actionId: selectedAction.actionId,
        transition: "reopened",
        reason: "试用中重新打开，保留此前确认记录。",
        at: new Date().toLocaleString("zh-CN", { hour12: false }),
        operator: "本机用户",
        reviewLabel: `第 ${nextIndex} 次重新核对`,
      },
    ]);
  };

  const selectedRecords =
    selectedAction === null
      ? []
      : manualRecords.filter((record) => record.actionId === selectedAction.actionId);
  const latestRecord = selectedRecords.at(-1) ?? null;
  const isConfirmedLocally = latestRecord?.transition === "closed";

  return (
    <div className="actions">
      <header className="page-head">
        <h1 className="page-head__title">行动中心</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：展示合成示例数据。人工确认会保留到本次浏览器会话结束，但不写入项目资料。
        </p>
      </header>

      <div className="actions-toolbar">
        <div className="chip-group" role="group" aria-label="按状态筛选">
          {STATE_FILTERS.map((option) => (
            <button
              key={option.key}
              type="button"
              className="chip"
              aria-pressed={stateFilter === option.key}
              onClick={() => setStateFilter(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="chip-group" role="group" aria-label="按阻断程度筛选">
          {BLOCKING_FILTERS.map((option) => (
            <button
              key={option.key}
              type="button"
              className="chip"
              aria-pressed={blockingFilter === option.key}
              onClick={() => setBlockingFilter(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <div className="chip-group" role="group" aria-label="按类别筛选">
          {CATEGORY_FILTERS.map((option) => (
            <button
              key={option.key}
              type="button"
              className="chip"
              aria-pressed={categoryFilter === option.key}
              onClick={() => setCategoryFilter(option.key)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>
      <p className="actions-toolbar__hint">
        {UI_PHRASES.actionCenterDenominator} {UI_PHRASES.provenanceFilterHint}
      </p>

      <div className="actions-layout">
        <section className="actions-list" aria-label="行动列表">
          <h2 className="actions-list__title">
            行动列表
            <span className="section-count">{filtered.length}</span>
          </h2>
          {filtered.length === 0 ? (
            <EmptyState
              message={UI_PHRASES.noTodos}
              hint="可调整状态、阻断程度或类别筛选后再看。"
            />
          ) : (
            <ul>
              {filtered.map((action) => {
                const actionRecords = manualRecords.filter(
                  (record) => record.actionId === action.actionId,
                );
                const locallyClosed = actionRecords.at(-1)?.transition === "closed";
                const displayState = locallyClosed
                  ? ("已在本次试用中关闭" as string)
                  : action.stateLabel;
                return (
                  <li key={action.actionId}>
                    <button
                      type="button"
                      className={`action-row${selectedAction?.actionId === action.actionId ? " action-row--selected" : ""}`}
                      aria-pressed={selectedAction?.actionId === action.actionId}
                      onClick={() =>
                        updateParams({ action: action.actionId })
                      }
                    >
                      <span className="action-row__codes">
                        <span className="action-row__subject">{action.subjectCode}</span>
                        <span className="action-row__stage">{action.dueStageLabel}</span>
                      </span>
                      <BlockingBadge level={action.blockingLevel} />
                      <span className="action-row__main">
                        <span className="action-row__text">
                          {action.requestedAction}
                        </span>
                        <span className="action-row__meta">
                          缺口：{action.gapLabel} · 责任方：{action.targetPartyLabel} ·{" "}
                          关联规则：{action.displayCode}
                        </span>
                      </span>
                      <span className="action-row__state">{displayState}</span>
                      <OpenIcon size={14} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <aside className="actions-detail" aria-label="行动详情">
          {selectedAction === null ? (
            <EmptyState
              message="选择一项行动查看详情。"
              hint="详情包含原因、责任方、可关闭证据、到期节点与人工确认记录。"
            />
          ) : (
            <article className="action-detail">
              <header className="action-detail__head">
                <h2 className="action-detail__title">
                  {selectedAction.subjectCode} · {selectedAction.displayCode}
                </h2>
                <div className="action-detail__badges">
                  <BlockingBadge level={selectedAction.blockingLevel} />
                  <span className="status-badge status-badge--neutral">
                    {isConfirmedLocally
                      ? "已在本次试用中关闭"
                      : selectedAction.stateLabel}
                  </span>
                </div>
              </header>

              <dl className="action-detail__grid">
                <div>
                  <dt>为什么需要</dt>
                  <dd>{selectedAction.gapLabel}（{selectedAction.blockingLabel}）</dd>
                </div>
                <div>
                  <dt>谁负责</dt>
                  <dd>{selectedAction.targetPartyLabel}</dd>
                </div>
                <div>
                  <dt>需要补什么</dt>
                  <dd>{selectedAction.requestedAction}</dd>
                </div>
                <div>
                  <dt>什么资料可以关闭</dt>
                  <dd>{selectedAction.acceptableEvidence}</dd>
                </div>
                <div>
                  <dt>到期节点</dt>
                  <dd>{selectedAction.dueStageLabel}</dd>
                </div>
                <div>
                  <dt>关联规则</dt>
                  <dd>{selectedAction.displayCode}</dd>
                </div>
                <div>
                  <dt>资料版本</dt>
                  <dd>第 {selectedAction.revision} 版</dd>
                </div>
              </dl>

              {componentDecision !== null && (
                <section className="action-detail__section">
                  <h3 className="action-detail__subtitle">关联规则当前判断</h3>
                  <p>
                    {selectedAction.displayCode} 当前判断为「
                    {componentDecision.decisionLabel}
                    」。关闭行动只表示该项缺口已处理或已有人工确认，
                    <strong>不等于规则自动通过</strong>；如判断变化需在新的资料整理后确认。
                  </p>
                </section>
              )}

              {selectedRecords.length > 0 && (
                <section className="action-detail__section">
                  <h3 className="action-detail__subtitle">人工操作记录（本次试用）</h3>
                  <ul className="action-detail__record">
                    {selectedRecords.map((record, index) => (
                      <li key={`${record.actionId}-${index}-${record.at}`}>
                        时间：{record.at} · 操作者：{record.operator} · 操作：{record.transition === "closed" ? "确认关闭" : "重新打开"}<br />
                        理由：{record.reason}<br />
                        后续：{record.reviewLabel}
                      </li>
                    ))}
                  </ul>
                  <p className="action-detail__note">
                    记录按发生顺序保留；重新打开不会删除此前记录。当前试用记录未写入项目资料。
                  </p>
                </section>
              )}

              {isConfirmedLocally && (
                <section className="action-detail__section">
                  <h3 className="action-detail__subtitle">本次确认前后差异</h3>
                  <ul className="judgment-pane__diffs">
                    <li className="judgment-diff">
                      <span className="judgment-diff__prior">
                        {componentDecision?.decisionLabel ?? "原判断"}
                      </span>
                      <span className="judgment-diff__arrow" aria-hidden="true">
                        →
                      </span>
                      <span className="judgment-diff__current">
                        需重新整理后确认
                      </span>
                    </li>
                  </ul>
                  <p className="action-detail__note">
                    正式使用时，行动关闭后会重新整理资料、更新规则判断，并在此处显示前后差异。
                  </p>
                </section>
              )}

              {selectedAction.state === "open" && !isConfirmedLocally && (
                <section className="action-detail__section action-detail__confirm">
                  <h3 className="action-detail__subtitle">人工确认（本次试用）</h3>
                  <label className="action-detail__reason-label" htmlFor="confirm-reason">
                    确认理由（必填）
                  </label>
                  <textarea
                    id="confirm-reason"
                    className="action-detail__reason"
                    rows={3}
                    placeholder="请用一句话说明：已查看哪些证据、为什么认为该项已处理。"
                    value={draftReason}
                    onChange={(event) => {
                      setDraftReason(event.target.value);
                      setConfirmError(null);
                    }}
                  />
                  {confirmError !== null && (
                    <p className="action-detail__error" role="alert">
                      {confirmError}
                    </p>
                  )}
                  <button
                    ref={confirmTriggerRef}
                    type="button"
                    className="button button--primary"
                    onClick={reviewConfirmation}
                  >
                    核对确认内容
                  </button>
                  <p className="action-detail__note">
                    本次确认只在当前页面暂时生效；无关文件不会关闭该行动。
                  </p>
                </section>
              )}

              {isConfirmedLocally && (
                <button
                  type="button"
                  className="button button--quiet"
                  onClick={reopenAction}
                >
                  重新打开
                </button>
              )}

              {manualRecords.length > 0 && (
                <button
                  type="button"
                  className="button button--quiet"
                  onClick={resetManualRecords}
                >
                  恢复试用初始状态
                </button>
              )}
            </article>
          )}
        </aside>
      </div>

      {showConfirmation && selectedAction !== null && (
        <div className="confirmation-scrim" onClick={closeConfirmation}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="manual-confirm-title"
            className="confirmation-dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="manual-confirm-title">确认本次人工处理</h2>
            <dl className="confirmation-dialog__details">
              <div><dt>对象</dt><dd>{selectedAction.subjectCode} · {selectedAction.displayCode}</dd></div>
              <div><dt>处理事项</dt><dd>{selectedAction.requestedAction}</dd></div>
              <div><dt>当前影响</dt><dd>{selectedAction.blockingLabel}；关闭行动不等于规则通过</dd></div>
              <div><dt>确认理由</dt><dd>{draftReason.trim()}</dd></div>
            </dl>
            <p className="confirmation-dialog__note">
              确认后将新增一条操作记录，并提示重新核对关联规则；原判断不会被直接改成通过。
            </p>
            <div className="confirmation-dialog__actions">
              <button ref={confirmBackRef} type="button" className="button" onClick={closeConfirmation}>
                返回修改
              </button>
              <button type="button" className="button button--primary" onClick={confirmAction}>
                确认关闭并重新核对
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default ActionsPage;
