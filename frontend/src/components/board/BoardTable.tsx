/**
 * 受试者 × 审核节点矩阵表（合同 §4.1）：TanStack Table v9 受控排序/选择。
 * - 每行一个受试者；每列一个独立审核节点（阶段永不合并）。
 * - 每格是直达入口（打开该受试者该节点的审核）。
 * - 排序/筛选只改变显示顺序；selection 以受试者 ID 为键，排序筛选后不丢失（§7.2）。
 * - 功能按需注册（rowSortingFeature/rowSelectionFeature），不引入 stockFeatures。
 */

import { useMemo } from "react";
import {
  createColumnHelper,
  createSortedRowModel,
  rowSelectionFeature,
  rowSortingFeature,
  tableFeatures,
  useTable,
  type RowSelectionState,
  type SortingState,
  type Updater,
} from "@tanstack/react-table";
import { RouteLink } from "../../app/router";
import { MainStatusBadge } from "../shell/StatusBadge";
import { OpenIcon, SortIcon } from "../shell/icons";
import { MAIN_STATUS_ORDER } from "../../domain/counts";
import type { ReviewStage } from "../../domain/enums";
import type {
  EpisodeCountsView,
  EpisodeSummaryView,
  SubjectSummaryView,
} from "../../domain/viewModels";

const features = tableFeatures({
  rowSortingFeature,
  sortedRowModel: createSortedRowModel(),
  rowSelectionFeature,
});

export const cellKey = (subjectId: string, stage: string): string =>
  `${subjectId}\u0000${stage}`;

export function CountsChips({ counts }: { counts: EpisodeCountsView }) {
  const items = [
    [counts.barrier, "明确障碍"],
    [counts.currentGap, "当前节点缺口"],
    [counts.conflict, "存在冲突"],
    [counts.professionalJudgment, "需专业判断"],
    [counts.provenanceFollowup, "溯源待办"],
    [counts.futureAttention, "后续节点关注"],
  ] as const;
  const visible = items.filter(([count]) => count > 0);
  if (visible.length === 0) {
    return <span className="episode-cell__counts">无缺口</span>;
  }
  return (
    <span className="episode-cell__counts">
      {visible.map(([count, label]) => (
        <span key={label} className="count-chip" title={label}>
          {label} {count}
        </span>
      ))}
    </span>
  );
}

export function EpisodeCell({ episode }: { episode: EpisodeSummaryView }) {
  return (
    <div className="episode-cell">
      <MainStatusBadge status={episode.mainStatus} />
      <CountsChips counts={episode.counts} />
      <RouteLink
        to="/workbench"
        params={{ episode: episode.episodeId }}
        className="icon-button episode-cell__open"
        ariaLabel={`打开 ${episode.subjectCode} ${episode.stageLabel}审核`}
        title={`打开 ${episode.subjectCode} ${episode.stageLabel}审核`}
      >
        <OpenIcon size={15} />
      </RouteLink>
    </div>
  );
}

function EmptyCell() {
  return <span className="episode-cell episode-cell--empty">该节点尚无资料</span>;
}

export interface BoardColumnContext {
  stages: ReadonlyArray<{ stage: ReviewStage; stageLabel: string }>;
  episodeIndex: ReadonlyMap<string, EpisodeSummaryView>;
  subjectRank: (subject: SubjectSummaryView) => number;
  countByStage: ReadonlyMap<ReviewStage, number>;
}

interface BoardTableProps extends BoardColumnContext {
  subjects: ReadonlyArray<SubjectSummaryView>;
  sorting: SortingState;
  onSortingChange: (updater: Updater<SortingState>) => void;
  rowSelection: RowSelectionState;
  onRowSelectionChange: (updater: Updater<RowSelectionState>) => void;
}

const helper = createColumnHelper<typeof features, SubjectSummaryView>();

export function BoardTable({
  subjects,
  stages,
  episodeIndex,
  subjectRank,
  countByStage,
  sorting,
  onSortingChange,
  rowSelection,
  onRowSelectionChange,
}: BoardTableProps) {
  const columns = useMemo(
    () =>
      helper.columns([
        helper.display({
          id: "select",
          header: ({ table }) => (
            <input
              type="checkbox"
              aria-label="全选当前筛选范围"
              checked={table.getIsAllRowsSelected()}
              ref={(element) => {
                if (element) element.indeterminate = table.getIsSomeRowsSelected();
              }}
              onChange={table.getToggleAllRowsSelectedHandler()}
            />
          ),
          cell: ({ row }) => (
            <input
              type="checkbox"
              aria-label={`选择 ${row.original.subjectCode}`}
              checked={row.getIsSelected()}
              onChange={row.getToggleSelectedHandler()}
            />
          ),
          enableSorting: false,
        }),
        helper.accessor("subjectCode", {
          header: "受试者",
          cell: ({ row }) => (
            <div className="board-subject">
              <span className="board-subject__code">{row.original.subjectCode}</span>
              <span className="board-subject__center">
                {row.original.centerCode} {row.original.centerName}
              </span>
            </div>
          ),
          sortFn: (rowA, rowB, columnId) =>
            rowA
              .getValue<string>(columnId)
              .localeCompare(rowB.getValue<string>(columnId), "zh"),
        }),
        helper.accessor((subject) => subjectRank(subject), {
          id: "blocking",
          header: "阻断程度",
          cell: ({ row }) => {
            const rank = subjectRank(row.original);
            if (rank >= MAIN_STATUS_ORDER.length) {
              return <span className="board-cell__muted">无审核节点</span>;
            }
            return <MainStatusBadge status={MAIN_STATUS_ORDER[rank]} />;
          },
          sortFn: (rowA, rowB, columnId) =>
            rowA.getValue<number>(columnId) - rowB.getValue<number>(columnId),
        }),
        ...stages.map(({ stage, stageLabel }) =>
          helper.accessor(
            (subject) => {
              const episode = episodeIndex.get(cellKey(subject.subjectId, stage));
              return episode === undefined
                ? MAIN_STATUS_ORDER.length
                : episode.sortRank;
            },
            {
              id: `stage-${stage}`,
              header: () => (
                <div className="board-stage-head">
                  <span className="board-stage-head__name">{stageLabel}</span>
                  <span className="board-stage-head__count">
                    {countByStage.get(stage) ?? 0} 个节点
                  </span>
                </div>
              ),
              cell: ({ row }) => {
                const episode = episodeIndex.get(
                  cellKey(row.original.subjectId, stage),
                );
                return episode === undefined ? (
                  <EmptyCell />
                ) : (
                  <EpisodeCell episode={episode} />
                );
              },
              sortFn: (rowA, rowB, columnId) =>
                rowA.getValue<number>(columnId) - rowB.getValue<number>(columnId),
            },
          ),
        ),
      ]),
    [stages, episodeIndex, subjectRank, countByStage],
  );

  const table = useTable({
    features,
    columns,
    data: [...subjects],
    getRowId: (row) => row.subjectId,
    enableSortingRemoval: false,
    // 首次点击一律升序（阻断程度按 0=明确障碍 最前），方向由用户后续点击切换
    sortDescFirst: false,
    state: { sorting, rowSelection },
    onSortingChange,
    onRowSelectionChange,
  });

  return (
    <div className="board-table-wrap">
      <table className="board-table">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => {
                const sorted = header.column.getIsSorted();
                const sortable = header.column.getCanSort();
                return (
                  <th
                    key={header.id}
                    aria-sort={
                      sorted === "asc"
                        ? "ascending"
                        : sorted === "desc"
                          ? "descending"
                          : undefined
                    }
                    className="board-table__th"
                  >
                    {header.isPlaceholder ? null : sortable ? (
                      <button
                        type="button"
                        className="board-table__sort"
                        title="点击排序"
                        onClick={(event) => {
                          header.column.getToggleSortingHandler()?.(event);
                        }}
                      >
                        <table.FlexRender header={header} />
                        {sorted !== false ? <SortIcon size={13} /> : null}
                      </button>
                    ) : (
                      <table.FlexRender header={header} />
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id}>
              {row.getAllCells().map((cell) => (
                <td key={cell.id} className="board-table__td">
                  <table.FlexRender cell={cell} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
