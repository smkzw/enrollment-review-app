/**
 * 项目看板（合同 §3.1 首屏候选之一 / §4.1）：受试者 × 独立审核节点矩阵。
 * - URL 参数驱动：stage（阶段聚焦）、status（主状态筛选）、sort/desc（排序）、q（受试者代号）。
 *   返回列表时筛选/排序自动恢复，页面不跳顶（§7.2）。
 * - 每格直达该受试者该审核节点；阶段永不合并为一个总状态。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { RowSelectionState, SortingState, Updater } from "@tanstack/react-table";
import { getDefaultRepository } from "../api";
import { updateParams, useHashRoute } from "../app/router";
import { useLoad } from "../app/useLoad";
import { EmptyState, ErrorState, LoadingState } from "../components/shell/Feedback";
import { BoardTable, cellKey } from "../components/board/BoardTable";
import { BoardToolbar, isStatusOption } from "../components/board/BoardToolbar";
import { StageSummaryBar } from "../components/board/StageSummaryBar";
import { blockingRank, countAllStages, MAIN_STATUS_ORDER } from "../domain/counts";
import { mainStatusLabel, stageLabel, UI_PHRASES } from "../domain/labels";
import type { ReviewStage } from "../domain/enums";
import type {
  BoardView,
  EpisodeSummaryView,
  SubjectSummaryView,
} from "../domain/viewModels";

function isStage(value: string | null): value is ReviewStage {
  return (
    value !== null &&
    ["pre_screening", "screening", "run_in", "baseline"].includes(value)
  );
}

function isValidSortColumn(id: string, board: BoardView): boolean {
  return (
    id === "subjectCode" ||
    id === "blocking" ||
    board.stages.some((stage) => `stage-${stage.stage}` === id)
  );
}

function selectSorting(
  board: BoardView,
  sortParam: string | null,
  descParam: string | null,
): SortingState {
  if (sortParam !== null && isValidSortColumn(sortParam, board)) {
    return [{ id: sortParam, desc: descParam === "1" }];
  }
  return [{ id: "subjectCode", desc: false }];
}

export function ProjectBoardPage() {
  const { state, retry } = useLoad(
    () => getDefaultRepository().getBoard(),
    [],
  );
  const { params } = useHashRoute();

  const board = state.status === "success" ? state.data : null;

  const stageParam = params.get("stage");
  const statusParam = params.get("status");
  const sortParam = params.get("sort");
  const descParam = params.get("desc");
  const query = params.get("q") ?? "";

  /** 受试者 × 阶段 → 审核节点索引 */
  const episodeIndex = useMemo(() => {
    const index = new Map<string, EpisodeSummaryView>();
    if (board === null) return index;
    for (const episode of board.episodes) {
      index.set(cellKey(episode.subjectId, episode.stage), episode);
    }
    return index;
  }, [board]);

  /** 可见阶段：聚焦某阶段时只显示该阶段列 */
  const visibleStages = useMemo(() => {
    if (board === null) return [];
    if (isStage(stageParam)) {
      return board.stages.filter((stage) => stage.stage === stageParam);
    }
    return board.stages;
  }, [board, stageParam]);

  /** 可见阶段内的审核节点（状态计数与筛选基数） */
  const visibleEpisodes = useMemo(() => {
    if (board === null) return [];
    const allowed = new Set(visibleStages.map((stage) => stage.stage));
    return board.episodes.filter((episode) => allowed.has(episode.stage));
  }, [board, visibleStages]);

  const statusOptions = useMemo(() => {
    return MAIN_STATUS_ORDER.map((status) => ({
      status,
      count: visibleEpisodes.filter((episode) => episode.mainStatus === status)
        .length,
    }));
  }, [visibleEpisodes]);

  /** 受试者过滤：状态筛选为受试者级（任一可见节点匹配即保留） */
  const filteredSubjects = useMemo(() => {
    if (board === null) return [];
    const statusFocus = isStatusOption(statusParam) ? statusParam : null;
    const normalizedQuery = query.trim().toLowerCase();
    return board.subjects.filter((subject) => {
      const episodes = visibleStages
        .map((stage) => episodeIndex.get(cellKey(subject.subjectId, stage.stage)))
        .filter((episode): episode is EpisodeSummaryView => episode !== undefined);
      if (episodes.length === 0) return false;
      if (statusFocus !== null) {
        if (!episodes.some((episode) => episode.mainStatus === statusFocus)) {
          return false;
        }
      }
      if (normalizedQuery !== "") {
        if (!subject.subjectCode.toLowerCase().includes(normalizedQuery)) {
          return false;
        }
      }
      return true;
    });
  }, [board, visibleStages, episodeIndex, statusParam, query]);

  /** 受试者级阻断程度：可见节点中的最差排序（0=明确障碍 … 5=未发现明确障碍） */
  const subjectRank = useCallback(
    (subject: SubjectSummaryView): number => {
      let worst = MAIN_STATUS_ORDER.length;
      for (const stage of visibleStages) {
        const episode = episodeIndex.get(cellKey(subject.subjectId, stage.stage));
        if (episode !== undefined) {
          worst = Math.min(worst, blockingRank(episode));
        }
      }
      return worst;
    },
    [visibleStages, episodeIndex],
  );

  const sorting = useMemo(
    () => (board === null ? [] : selectSorting(board, sortParam, descParam)),
    [board, sortParam, descParam],
  );

  const handleSortingChange = useCallback(
    (updater: Updater<SortingState>) => {
      const next =
        typeof updater === "function" ? updater(sorting) : updater;
      const primary = next[0];
      updateParams({
        sort: primary === undefined ? undefined : primary.id,
        desc: primary?.desc === true ? "1" : undefined,
      });
    },
    [sorting],
  );

  const countByStage = useMemo(() => {
    const map = new Map<ReviewStage, number>();
    if (board === null) return map;
    for (const episode of board.episodes) {
      map.set(episode.stage, (map.get(episode.stage) ?? 0) + 1);
    }
    return map;
  }, [board]);

  /** 勾选：以受试者 ID 为键，排序/筛选后不丢失（§7.2） */
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const selectedSubjects = board?.subjects.filter(
    (subject) => rowSelection[subject.subjectId] === true,
  ) ?? [];
  const selectedCount = selectedSubjects.length;
  const [showBatchConfirmation, setShowBatchConfirmation] = useState(false);
  const [batchSummary, setBatchSummary] = useState<ReadonlyArray<string>>([]);
  const batchTriggerRef = useRef<HTMLButtonElement>(null);
  const batchBackRef = useRef<HTMLButtonElement>(null);

  const closeBatchConfirmation = useCallback(() => {
    setShowBatchConfirmation(false);
    requestAnimationFrame(() => batchTriggerRef.current?.focus());
  }, []);

  useEffect(() => {
    if (!showBatchConfirmation) return;
    batchBackRef.current?.focus();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeBatchConfirmation();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [closeBatchConfirmation, showBatchConfirmation]);

  const handleSelectionChange = useCallback(
    (updater: Updater<RowSelectionState>) => {
      setRowSelection((current) =>
        typeof updater === "function" ? updater(current) : updater,
      );
    },
    [],
  );

  if (state.status === "loading") {
    return <LoadingState />;
  }
  if (state.status === "error" || board === null) {
    return <ErrorState message={state.status === "error" ? state.message : UI_PHRASES.temporarilyUnavailable} onRetry={retry} />;
  }

  const summaries = countAllStages(board.episodes);
  const statusFocus = isStatusOption(statusParam) ? statusParam : null;
  const stageFocus = isStage(stageParam) ? stageParam : null;
  /** 阶段筛选/列头使用合同固定短词（预筛期/筛选期/…），不用 fixture 展示名 */
  const stageOptions = board.stages.map((stage) => ({
    stage: stage.stage,
    stageLabel: stageLabel[stage.stage],
  }));
  const positionNote =
    stageFocus !== null
      ? `当前范围：${stageLabel[stageFocus]}${statusFocus !== null ? ` · ${mainStatusLabel[statusFocus]}` : ""}`
      : statusFocus !== null
        ? `当前范围：全部阶段 · ${mainStatusLabel[statusFocus]}`
        : "当前范围：全部阶段";

  const clearFilters = () => {
    updateParams({ stage: null, status: null, sort: null, desc: null, q: null });
    setRowSelection({});
  };

  return (
    <div className="board">
      <header className="page-head">
        <h1 className="page-head__title">项目看板</h1>
        <p className="page-head__note">
          {UI_PHRASES.prototypeOnly}：展示合成示例数据。{positionNote}
        </p>
      </header>

      <StageSummaryBar summaries={summaries} />

      <BoardToolbar
        stages={stageOptions}
        stageFocus={stageFocus}
        statusFocus={statusFocus}
        statusOptions={statusOptions}
        query={query}
        onStageChange={(stage) => updateParams({ stage: stage ?? null })}
        onStatusChange={(status) => updateParams({ status: status ?? null })}
        onQueryChange={(value) => updateParams({ q: value === "" ? null : value })}
      />

      {selectedCount > 0 && (
        <div className="board-selection" role="status">
          <span>
            已选择 {selectedCount} 位受试者（只处理明确勾选对象）
          </span>
          <button
            ref={batchTriggerRef}
            type="button"
            className="button button--primary"
            onClick={() => setShowBatchConfirmation(true)}
          >
            批量回看审核摘要
          </button>
          <button
            type="button"
            className="button button--quiet"
            onClick={() => setRowSelection({})}
          >
            清除选择
          </button>
        </div>
      )}

      {batchSummary.length > 0 && (
        <section className="board-batch-result" aria-live="polite">
          <strong>批量操作完成</strong>
          <span>本次只回看以下 {batchSummary.length} 位受试者，不改变任何审核结论：</span>
          <span>{batchSummary.join("、")}</span>
        </section>
      )}

      {filteredSubjects.length === 0 ? (
        <div className="board-empty">
          <EmptyState
            message={UI_PHRASES.empty}
            hint="可调整阶段、状态或代号筛选后再试。"
          />
          <button type="button" className="button" onClick={clearFilters}>
            清除筛选
          </button>
        </div>
      ) : (
        <BoardTable
          subjects={filteredSubjects}
          stages={visibleStages.map((stage) => ({
            stage: stage.stage,
            stageLabel: stageLabel[stage.stage],
          }))}
          episodeIndex={episodeIndex}
          subjectRank={subjectRank}
          countByStage={countByStage}
          sorting={sorting}
          onSortingChange={handleSortingChange}
          rowSelection={rowSelection}
          onRowSelectionChange={handleSelectionChange}
        />
      )}

      {showBatchConfirmation && (
        <div className="confirmation-scrim" onClick={closeBatchConfirmation}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="batch-confirm-title"
            className="confirmation-dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <h2 id="batch-confirm-title">确认批量操作范围</h2>
            <p>本次操作：回看审核摘要，不改变审核结论。</p>
            <p>明确勾选 {selectedSubjects.length} 位受试者：</p>
            <ul className="confirmation-dialog__list">
              {selectedSubjects.map((subject) => (
                <li key={subject.subjectId}>{subject.subjectCode} · {subject.centerCode} {subject.centerName}</li>
              ))}
            </ul>
            <p className="confirmation-dialog__note">
              未显示或未勾选的受试者不会被加入。排序和筛选不会扩大以上范围。
            </p>
            <div className="confirmation-dialog__actions">
              <button ref={batchBackRef} type="button" className="button" onClick={closeBatchConfirmation}>
                返回检查
              </button>
              <button
                type="button"
                className="button button--primary"
                onClick={() => {
                  setBatchSummary(selectedSubjects.map((subject) => subject.subjectCode));
                  setShowBatchConfirmation(false);
                }}
              >
                确认回看
              </button>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

export default ProjectBoardPage;
