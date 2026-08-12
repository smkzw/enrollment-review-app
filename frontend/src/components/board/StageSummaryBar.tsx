/**
 * 各审核阶段汇总条：节点总数与六类主状态计数（合同 §4.1）。
 * 计数以 fixture rollup 为准，前端不重新推导结论。
 */

import type { StageCountSummary } from "../../domain/counts";

export function StageSummaryBar({
  summaries,
}: {
  summaries: ReadonlyArray<StageCountSummary>;
}) {
  return (
    <div className="stage-summary" aria-label="各审核阶段节点汇总">
      {summaries.map((summary) => {
        const visible = summary.byMainStatus.filter((item) => item.count > 0);
        return (
          <div key={summary.stage} className="stage-summary__item">
            <span className="stage-summary__name">{summary.stageLabel}</span>
            <span className="stage-summary__total">
              {summary.total} 个节点
            </span>
            <span className="stage-summary__chips">
              {visible.length === 0 ? (
                <span className="stage-summary__none">无节点</span>
              ) : (
                visible.map(({ label, count }) => (
                  <span key={label} className="count-chip" title={label}>
                    {label} {count}
                  </span>
                ))
              )}
            </span>
          </div>
        );
      })}
    </div>
  );
}
