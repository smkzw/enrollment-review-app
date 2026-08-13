/**
 * 定位精度组件（合同 §6.1 四级定位视觉诚实性）。
 * - 每次显示证据都同时呈现精度中文词、图标与说明；形状/色调共同区分四级，不只用颜色。
 * - 仅页码/页内摘录项绝不显示坐标框或虚假高亮；界面试用阶段不附带原始页图，不绘制任何 bbox 框。
 */

import type { LocatorPrecision } from "../../domain/enums";
import { precisionLabel, UI_PHRASES } from "../../domain/labels";
import { BboxIcon, ExcerptIcon, PageOnlyIcon, TextRangeIcon } from "../shell/icons";

/** 每个精度等级固定可见的诚实说明（§6.1 允许/禁止的视觉效果）。 */
export const PRECISION_DESCRIPTIONS: Record<LocatorPrecision, string> = {
  bbox: "可定位到原始页图上的具体文字位置（坐标区域）。当前界面未附带页图，不绘制坐标框。",
  text_range: "可定位到识别文字中的一段文字范围，并显示页码与摘录。",
  page_excerpt: "可定位到页内摘录区域，但不能精确到具体字符位置。",
  page_only:
    "只能确定到整页，没有文字坐标或文本高亮；界面试用阶段未附带原始页图，不提供整页预览。",
};

export const PRECISION_ORDER: readonly LocatorPrecision[] = [
  "bbox",
  "text_range",
  "page_excerpt",
  "page_only",
];

function precisionIcon(precision: LocatorPrecision, size = 13) {
  switch (precision) {
    case "bbox":
      return <BboxIcon size={size} />;
    case "text_range":
      return <TextRangeIcon size={size} />;
    case "page_excerpt":
      return <ExcerptIcon size={size} />;
    case "page_only":
      return <PageOnlyIcon size={size} />;
  }
}

interface PrecisionBadgeProps {
  precision: LocatorPrecision;
  /** 是否附带完整说明作为悬停提示 */
  hint?: boolean;
}

/** 精度徽标：中文词 + 图标 + 形状差异，色调只作辅助。 */
export function PrecisionBadge({ precision, hint = true }: PrecisionBadgeProps) {
  return (
    <span
      className={`precision-badge precision-badge--${precision}`}
      title={hint ? PRECISION_DESCRIPTIONS[precision] : precisionLabel[precision]}
    >
      {precisionIcon(precision)}
      <span>{precisionLabel[precision]}</span>
    </span>
  );
}

/** 四级定位图例：证据区顶部固定显示，保证用户能区分并理解各精度含义。 */
export function PrecisionLegend() {
  return (
    <div className="precision-legend" aria-label="定位精度说明">
      {PRECISION_ORDER.map((precision) => (
        <div key={precision} className="precision-legend__item">
          <PrecisionBadge precision={precision} />
          <span className="precision-legend__desc">
            {PRECISION_DESCRIPTIONS[precision]}
          </span>
        </div>
      ))}
      <p className="precision-legend__note">
        {UI_PHRASES.precisionPrefix}与{UI_PHRASES.degradationPrefix}均以中文说明为准；
        没有坐标数据时不会显示任何高亮或定位框。
      </p>
    </div>
  );
}
