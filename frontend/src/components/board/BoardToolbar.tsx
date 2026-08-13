/**
 * 看板工具栏：阶段筛选、状态筛选（含计数）与受试者代号检索。
 * 全部为受控筛选，状态经 URL 参数保存（合同 §4.1/7.2：返回列表后筛选保留）。
 */

import { isAdditiveCategory, MAIN_STATUS_ORDER } from "../../domain/counts";
import { mainStatusLabel, UI_PHRASES } from "../../domain/labels";
import type { EpisodeMainStatus, ReviewStage } from "../../domain/enums";

export interface StatusFilterOption {
  status: EpisodeMainStatus;
  count: number;
}

interface BoardToolbarProps {
  stages: ReadonlyArray<{ stage: ReviewStage; stageLabel: string }>;
  stageFocus: ReviewStage | null;
  statusFocus: EpisodeMainStatus | null;
  statusOptions: ReadonlyArray<StatusFilterOption>;
  query: string;
  onStageChange: (stage: ReviewStage | null) => void;
  onStatusChange: (status: EpisodeMainStatus | null) => void;
  onQueryChange: (query: string) => void;
}

export function BoardToolbar({
  stages,
  stageFocus,
  statusFocus,
  statusOptions,
  query,
  onStageChange,
  onStatusChange,
  onQueryChange,
}: BoardToolbarProps) {
  return (
    <div className="board-toolbar">
      <div className="board-toolbar__row">
        <span className="board-toolbar__label" id="board-stage-filter-label">
          审核阶段
        </span>
        <div
          className="chip-group"
          role="group"
          aria-labelledby="board-stage-filter-label"
        >
          <button
            type="button"
            className="chip"
            aria-pressed={stageFocus === null}
            onClick={() => onStageChange(null)}
          >
            全部阶段
          </button>
          {stages.map(({ stage, stageLabel }) => (
            <button
              key={stage}
              type="button"
              className="chip"
              aria-pressed={stageFocus === stage}
              onClick={() => onStageChange(stageFocus === stage ? null : stage)}
            >
              {stageLabel}
            </button>
          ))}
        </div>
      </div>
      <div className="board-toolbar__row">
        <span className="board-toolbar__label" id="board-status-filter-label">
          节点状态
        </span>
        <div
          className="chip-group"
          role="group"
          aria-labelledby="board-status-filter-label"
        >
          <button
            type="button"
            className="chip"
            aria-pressed={statusFocus === null}
            onClick={() => onStatusChange(null)}
          >
            全部状态
          </button>
          {statusOptions.map(({ status, count }) => (
            <button
              key={status}
              type="button"
              className="chip"
              aria-pressed={statusFocus === status}
              title={
                isAdditiveCategory(status)
                  ? UI_PHRASES.additiveCategoryTitle
                  : undefined
              }
              onClick={() =>
                onStatusChange(statusFocus === status ? null : status)
              }
            >
              {mainStatusLabel[status]} {count}
            </button>
          ))}
        </div>
      </div>
      <div className="board-toolbar__row board-toolbar__search-row">
        <label className="board-search">
          <span>受试者代号</span>
          <input
            type="search"
            value={query}
            placeholder="如 UAT-03"
            aria-label="按受试者代号筛选"
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </label>
      </div>
      <p className="board-toolbar__hint">{UI_PHRASES.boardCountHint}</p>
    </div>
  );
}

export function isStatusOption(
  value: string | null,
): value is EpisodeMainStatus {
  return MAIN_STATUS_ORDER.includes(value as EpisodeMainStatus);
}
