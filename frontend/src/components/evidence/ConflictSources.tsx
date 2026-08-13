/**
 * 冲突来源并列（合同 §6.2 / B1、F6 修复）：未解决冲突组内每个事实
 * 并列展示立场、值与其来源定位（文件、资料快照版本、页码、摘录、精度）。
 * - 不自动选择其中一方；每条来源可打开证据详情弹窗。
 * - 原始组件/事实 ID 不作为主标签出现。
 */

import type {
  ConflictGroupView,
  EvidenceLocatorView,
} from "../../domain/viewModels";
import { UI_PHRASES } from "../../domain/labels";
import { factTypeDisplayName } from "../review/attributes";
import { EvidenceCard } from "./EvidenceCard";
import type { SourceDocumentView } from "./EvidenceDialog";

export interface ConflictSourcesProps {
  conflicts: ReadonlyArray<ConflictGroupView>;
  sourceDocuments: ReadonlyArray<SourceDocumentView>;
}

export function ConflictSources({
  conflicts,
  sourceDocuments,
}: ConflictSourcesProps) {
  const unresolved = conflicts.filter((group) => !group.resolved);
  if (unresolved.length === 0) return null;

  const sourceOf = (
    locator: EvidenceLocatorView,
  ): SourceDocumentView | undefined =>
    sourceDocuments.find(
      (document) => document.documentVersionId === locator.documentVersionId,
    );

  return (
    <div className="conflict-sources" aria-label={UI_PHRASES.conflictSourcesTitle}>
      <h3 className="workbench-pane__subtitle">
        {UI_PHRASES.conflictSourcesTitle}
      </h3>
      <p className="conflict-sources__hint">{UI_PHRASES.conflictSourcesHint}</p>
      <ul className="conflict-sources__list">
        {unresolved.map((group) => (
          <li key={group.conflictGroupId} className="conflict-group">
            <header className="conflict-group__head">
              <span className="conflict-group__code">
                {UI_PHRASES.conflictAffectedCode}：
                {group.affectedDisplayCodes.join("、")}
              </span>
              <span className="conflict-group__snapshot">
                资料快照：{group.snapshotVersion}
              </span>
            </header>
            <div className="conflict-group__facts">
              {group.facts.map((fact) => {
                const factName = factTypeDisplayName(fact.factType);
                return (
                  <div key={fact.factId} className="conflict-fact">
                    <p className="conflict-fact__stance">
                      <span className="conflict-fact__polarity">
                        {fact.polarityLabel}
                      </span>
                      {factName !== null && (
                        <span className="conflict-fact__name">{factName}</span>
                      )}
                      {fact.value !== null &&
                        typeof fact.value !== "boolean" && (
                          <span className="conflict-fact__value">
                            {UI_PHRASES.conflictStanceValue}：{String(fact.value)}
                          </span>
                        )}
                    </p>
                    {fact.evidence.length === 0 ? (
                      <p className="conflict-fact__muted">
                        {UI_PHRASES.conflictNoSource}
                      </p>
                    ) : (
                      <ul className="conflict-fact__evidence">
                        {fact.evidence.map((locator) => (
                          <li key={locator.spanId}>
                            <EvidenceCard
                              locator={locator}
                              source={sourceOf(locator)}
                            />
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
