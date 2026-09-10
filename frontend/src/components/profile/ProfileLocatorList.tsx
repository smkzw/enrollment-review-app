/**
 * Patient Profile 定位详情（Slice 5.6）：列出选中条目的原文定位。
 * - 所有可用定位都可打开所在页；只有已核验的原文区域会画唯一单框；
 * - 页内摘录 / 仅页码等定位只导航到对应页，绝不合成区域或画框；
 * - 冲突条目按并列记录分列，方便逐条对照原件。
 */

import type { LocatorView } from "../../api/evidence";
import type { ProfileItemView } from "../../api/patient-profile";

/** 定位是否为真实区域（可画唯一红框的前提）。 */
export function isRealBboxLocator(locator: LocatorView): boolean {
  return (
    locator.precision === "bbox" &&
    locator.authenticity === "authenticated" &&
    locator.bbox !== null &&
    locator.coordinateFrame !== null
  );
}

function authenticityLabel(locator: LocatorView): string {
  switch (locator.authenticity) {
    case "authenticated":
      return "已核验";
    case "degraded":
      return "定位范围有限";
    case "rejected":
      return "未采用";
  }
}

export interface ProfileLocatorListProps {
  item: ProfileItemView;
  locators: ReadonlyArray<LocatorView>;
  selectedLocatorId: string | null;
  onSelectLocator: (locatorId: string) => void;
}

export function ProfileLocatorList({
  item,
  locators,
  selectedLocatorId,
  onSelectLocator,
}: ProfileLocatorListProps) {
  const isConflict = item.kind === "conflict";
  if (locators.length === 0) {
    return (
      <p className="profile-evidence__muted">
        该条目没有可查看的原文定位。
      </p>
    );
  }
  return (
    <div className={isConflict ? "profile-locator-juxtapose" : "profile-locator-list"}>
      {locators.map((locator, index) => {
        const real = isRealBboxLocator(locator);
        const selected = locator.locatorId === selectedLocatorId;
        return (
          <article
            key={locator.locatorId}
            className={`profile-locator${selected ? " profile-locator--selected" : ""}`}
            aria-label={
              isConflict
                ? `并列记录 ${index + 1}：${locator.precisionLabel}`
                : `定位 ${index + 1}：${locator.precisionLabel}`
            }
          >
            <header className="profile-locator__head">
              <strong className="profile-locator__precision">
                {isConflict
                  ? `并列记录 ${index + 1} · ${locator.precisionLabel}`
                  : locator.precisionLabel}
              </strong>
              <span className="count-chip profile-locator__authenticity">
                {authenticityLabel(locator)}
              </span>
            </header>
            <p className="profile-locator__meta">
              第 {locator.pageNumber} 页 · {locator.sourceLayerLabel}
            </p>
            {locator.excerpt !== null && locator.excerpt.length > 0 && (
              <p className="profile-locator__excerpt">{locator.excerpt}</p>
            )}
            {locator.degradationReason !== null && (
              <p className="profile-locator__reason">{locator.degradationReason}</p>
            )}
            <p className="profile-locator__precision-note">
              {real
                ? "已精确定位到原文区域。"
                : locator.precision === "page_only"
                  ? "只能确定到所在页，将打开整页查看，不显示重点框。"
                  : "可按文字位置回看原文，但无法稳定框出具体区域。"}
            </p>
            <button
              type="button"
              className={`chip profile-locator__locate${selected ? " is-active" : ""}`}
              aria-pressed={selected}
              onClick={() => onSelectLocator(locator.locatorId)}
            >
              {real
                ? selected
                  ? "当前定位"
                  : "定位到原文"
                : selected
                  ? "当前页"
                  : "查看所在页"}
            </button>
          </article>
        );
      })}
    </div>
  );
}
