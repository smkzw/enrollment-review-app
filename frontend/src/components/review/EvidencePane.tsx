/**
 * 证据区（工作台第三区）：识别文字 + 原始文件证据 + 应备证据覆盖（合同 §5.2/§6.1）。
 * - 顶部固定四级定位精度图例；每条证据显示文件、页码、精度与降级原因。
 * - 应备证据覆盖区分“已找到/证据较弱/已引用但未提供/尚未见到/后续尚未到期”。
 * - 选中证据后弹窗显示原始资料信息与识别文字，不绘制虚假坐标高亮。
 */

import { useState } from "react";
import type {
  ConflictGroupView,
  EvidenceExpectationView,
  EvidenceLocatorView,
  RuleComponentView,
} from "../../domain/viewModels";
import type { SourceDocumentView } from "../evidence/EvidenceDialog";
import { ConflictSources } from "../evidence/ConflictSources";
import { EvidenceCard } from "../evidence/EvidenceCard";
import { PrecisionLegend } from "../evidence/PrecisionBadge";
import { EmptyState } from "../shell/Feedback";
import { UI_PHRASES } from "../../domain/labels";

export interface EvidencePaneProps {
  component: RuleComponentView | null;
  expectations: ReadonlyArray<EvidenceExpectationView>;
  /** 节点全部未解决冲突组（并列来源展示） */
  conflicts: ReadonlyArray<ConflictGroupView>;
  sourceDocuments: ReadonlyArray<SourceDocumentView>;
  /** 从其他页面直达的证据（自动展开定位到该条） */
  focusSpanId?: string | null;
  /** 可滚动面板的键盘焦点入口（axe scrollable-region-focusable） */
  paneTabIndex?: number;
}

const EXPECTATION_ORDER = ["observed", "observed_weak", "referenced_missing", "absent", "not_due", "pending_control_applicability"] as const;

export function EvidencePane({
  component,
  expectations,
  conflicts,
  sourceDocuments,
  focusSpanId,
  paneTabIndex = 0,
}: EvidencePaneProps) {
  const [highlighted, setHighlighted] = useState<string | null>(
    focusSpanId ?? null,
  );

  if (component === null) {
    return (
      <div className="workbench-pane workbench-pane--empty" tabIndex={paneTabIndex}>
        <p className="workbench-pane__empty-title">尚未选择规则子项</p>
        <p className="workbench-pane__empty-hint">
          在规则区选择一项子规则后，这里会显示与它相关的识别文字、原始文件证据和应备证据覆盖。
        </p>
      </div>
    );
  }

  const sourceOf = (locator: EvidenceLocatorView): SourceDocumentView | undefined =>
    sourceDocuments.find(
      (document) => document.documentVersionId === locator.documentVersionId,
    );

  const evidence = [...component.evidence].sort(
    (a, b) =>
      a.pageNumber - b.pageNumber ||
      a.fileName.localeCompare(b.fileName, "zh"),
  );

  return (
    <section
      className="workbench-pane evidence-pane"
      aria-label="识别文字与原始证据"
      tabIndex={paneTabIndex}
    >
      <header className="workbench-pane__head">
        <h2 className="workbench-pane__title">
          <span className="workbench-pane__code">{component.displayCode}</span>
          证据与原始资料
        </h2>
      </header>

      <ConflictSources
        conflicts={conflicts}
        sourceDocuments={sourceDocuments}
      />

      <PrecisionLegend />

      <div className="workbench-pane__section">
        <h3 className="workbench-pane__subtitle">相关证据（当前子项）</h3>
        {evidence.length === 0 ? (
          <EmptyState message={UI_PHRASES.empty} hint="该子项尚无可用证据定位。" />
        ) : (
          <ul className="evidence-pane__list">
            {evidence.map((locator) => (
              <li
                key={locator.spanId}
                className={
                  highlighted === locator.spanId
                    ? "evidence-pane__item evidence-pane__item--focus"
                    : "evidence-pane__item"
                }
              >
                <EvidenceCard
                  locator={locator}
                  source={sourceOf(locator)}
                  onOpen={(selected) => setHighlighted(selected.spanId)}
                />
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="workbench-pane__section">
        <h3 className="workbench-pane__subtitle">
          {UI_PHRASES.expectationNodeWideTitle}
        </h3>
        <p className="workbench-pane__muted">{UI_PHRASES.expectationNodeWideHint}</p>
        {expectations.length === 0 ? (
          <p className="workbench-pane__muted">当前没有应备证据要求。</p>
        ) : (
          <ul className="expectation-list">
            {[...expectations]
              .sort(
                (a, b) =>
                  EXPECTATION_ORDER.indexOf(a.status as (typeof EXPECTATION_ORDER)[number]) -
                  EXPECTATION_ORDER.indexOf(b.status as (typeof EXPECTATION_ORDER)[number]),
              )
              .map((expectation) => (
                <li key={expectation.expectationId} className="expectation-row">
                  <span className="expectation-row__code">
                    {expectation.displayCode}
                  </span>
                  <span
                    className={`status-badge status-badge--expectation status-badge--expectation-${expectation.status}`}
                  >
                    {expectation.statusLabel}
                  </span>
                  <span className="expectation-row__gap">{expectation.gapLabel}</span>
                  {expectation.requirementDescription !== "" && (
                    <span className="expectation-row__desc">
                      {expectation.requirementDescription}
                    </span>
                  )}
                  <span className="expectation-row__stage">
                    到期节点：{expectation.dueStageLabel}
                  </span>
                  {expectation.evidenceSpanIds.length > 0 && (
                    <span className="expectation-row__count">
                      {expectation.evidenceSpanIds.length} 处证据
                    </span>
                  )}
                </li>
              ))}
          </ul>
        )}
      </div>
    </section>
  );
}
