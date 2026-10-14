import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, X } from "lucide-react";
import type { ProfileItemView, ProfileLaneWire } from "../../api/patient-profile";
import { clinicalDisplayLanes, profileDateRoleLabel, type PatientProfileModel } from "../../features/patient-profile/model";
import { ProfileItemCard } from "./ProfileItemCard";

const historyLanes: readonly ProfileLaneWire[] = ["target_disease", "symptoms_signs", "medical_history", "allergy_infection_immune", "special_history"];
const treatmentLanes: readonly ProfileLaneWire[] = ["medication", "non_drug_treatment"];

/** Display the recorded date and its purpose, not an inferred occurrence or upload date. */
export function timelineTime(item: ProfileItemView) {
  const range = item.startRange;
  if (!range || !range.sourceText && !range.lowerBound && !range.upperBound) {
    return { key: "unknown", label: "日期未明确", role: null, sort: null };
  }
  const role = profileDateRoleLabel(item);
  const lower = range.lowerBound;
  const upper = range.upperBound;
  let label = range.sourceText || [lower, upper].filter(Boolean).join(" 至 ");
  // Keep the original precision: a month never becomes a specific occurrence day.
  if (lower && upper && range.precision === "day" && lower === upper) label = lower;
  else if (lower && upper && range.precision === "month" && lower.slice(0, 7) === upper.slice(0, 7)) {
    label = `${lower.slice(0, 4)}年${Number(lower.slice(5, 7))}月`;
  } else if (lower && upper && range.precision === "year" && lower.slice(0, 4) === upper.slice(0, 4)) {
    label = `${lower.slice(0, 4)}年`;
  }
  return { key: JSON.stringify([role, range.precision, lower, upper, label]), label, role,
    sort: lower };
}

function title(item: ProfileItemView) { return item.assertedObject || item.medicationName || item.title; }
function valueText(item: ProfileItemView) {
  return item.value === null || typeof item.value === "boolean" ? "" : `${item.value}${item.unit && item.unit !== "unitless" ? ` ${item.unit}` : ""}`;
}
function day(value: string | null | undefined) { const time = value ? Date.parse(`${value}T00:00:00Z`) : NaN; return Number.isFinite(time) ? time : null; }

export function clinicalSpan(item: ProfileItemView) {
  const start = day(item.startRange?.lowerBound);
  if (start === null) return null;
  const explicitEnd = item.kind !== "fact" ? day(item.endRange?.upperBound) : null;
  const end = explicitEnd ?? day(item.startRange?.upperBound) ?? start;
  if (end < start) return null;
  return { start, end, interval: explicitEnd !== null,
    uncertain: item.startRange?.precision !== "day" || explicitEnd !== null && item.endRange?.precision !== "day" };
}

function ClinicalChart({ label, tone, items, selectedId, onSelect }: {
  label: string; tone: "history" | "treatment"; items: ProfileItemView[];
  selectedId: string | null; onSelect: (id: string) => void;
}) {
  const [recent, setRecent] = useState(false);
  const spans = items.map(item => ({ item, span: clinicalSpan(item) }));
  const dates = spans.flatMap(({ span }) => span ? [span.start, span.end] : []);
  const latest = dates.length ? Math.max(...dates) : 0;
  const cutoffDate = new Date(latest); cutoffDate.setUTCFullYear(cutoffDate.getUTCFullYear() - 1);
  const cutoff = cutoffDate.getTime();
  const visible = recent ? spans.filter(({ span }) => !span || span.end >= cutoff) : spans;
  const timed = visible.filter(value => value.span !== null);
  const bounds = timed.flatMap(({ span }) => [span!.start, span!.end]);
  const lower = bounds.length ? Math.min(...bounds) : 0;
  const upper = bounds.length ? Math.max(...bounds) : 0;
  const padding = Math.max((upper - lower) * .035, 86400000 * 2);
  const min = lower - padding, max = upper + padding;
  const percent = (time: number) => (time - min) / (max - min) * 100;
  const rows = new Map<string, typeof spans>();
  for (const record of visible) {
    const key = `${record.item.lane}:${title(record.item).normalize("NFKC").replace(/\s/g, "")}`;
    rows.set(key, [...(rows.get(key) ?? []), record]);
  }
  const ticks = [0, 1, 2, 3, 4].map(tick => min + (max - min) * tick / 4);
  const formatTicks = (month: boolean, fullDay: boolean) => ticks.map(time => new Intl.DateTimeFormat("zh-CN", {
    timeZone: "UTC", year: "numeric", ...(month ? { month: "numeric" as const } : {}),
    ...(fullDay ? { day: "numeric" as const } : {}),
  }).format(time));
  let tickLabels = formatTicks(max - min < 86400000 * 800, false);
  if (new Set(tickLabels).size !== ticks.length) tickLabels = formatTicks(true, false);
  if (new Set(tickLabels).size !== ticks.length) tickLabels = formatTicks(true, true);
  return <section className={`clinical-chart clinical-chart--${tone}`} aria-label={`${label}时间图`}>
    <header className="clinical-chart__head"><h3>{label}</h3>
      {dates.length > 0 && <div role="group" aria-label={`${label}时间范围`}>
        <button type="button" aria-pressed={!recent} onClick={() => setRecent(false)}>全部时间</button>
        <button type="button" aria-pressed={recent} onClick={() => setRecent(true)}>近一年</button>
      </div>}
    </header>
    {timed.length > 0 && <div className="clinical-chart__axis"><span />
      <div>{tickLabels.map((label, tick) => <span key={tick} style={{ left: `${tick * 25}%` }}>{label}</span>)}</div>
    </div>}
    {recent && spans.length > visible.length && <button type="button" className="clinical-chart__earlier" onClick={() => setRecent(false)}>查看更早的 {spans.length - visible.length} 条记录</button>}
    {[true, false].map(dated => {
      const group = [...rows.entries()].filter(([, records]) => records.some(record => record.span !== null) === dated);
      const content = group.map(([key, records]) => {
      const slots: number[] = [];
      const points = [...records].sort((a, b) => (a.span?.start ?? Infinity) - (b.span?.start ?? Infinity)).flatMap(({ item, span }) => {
        if (!span) return [];
        const left = percent(span.start), right = percent(span.end);
        let slot = slots.findIndex(last => left - last >= 5);
        if (slot < 0) slot = slots.length;
        slots[slot] = right;
        return [{ item, span, left, right, slot }];
      });
      const unknown = records.filter(record => !record.span);
      return <div key={key} className="clinical-chart__row"><strong>{title(records[0]!.item)}</strong>
        <div className={`clinical-chart__track${points.length ? "" : " clinical-chart__track--undated"}`} style={{ minHeight: `${Math.max(1, slots.length) * 1.8}rem` }}>
          {points.map(({ item, span, left, right, slot }) => <button type="button" key={item.itemId}
            className={`clinical-chart__point${span.interval ? " is-interval" : right > left ? " is-range" : ""}${span.uncertain ? " is-uncertain" : ""}`}
            style={{ left: `${left}%`, width: right > left ? `max(1rem, ${right - left}%)` : undefined, top: `${slot * 1.8 + .5}rem` }}
            aria-pressed={selectedId === item.itemId}
            aria-label={`${title(item)}，${timelineTime(item).label}${valueText(item) ? `，${valueText(item)}` : ""}`}
            title={`${title(item)}\n${profileDateRoleLabel(item) ?? "原文日期"}：${timelineTime(item).label}${item.endRange ? ` 至 ${item.endRange.sourceText ?? item.endRange.upperBound ?? "未明确"}` : ""}\n${span.interval ? "明确起止区间" : span.uncertain ? "日期范围，非持续用药时长" : "日期点"}\n${valueText(item)}`}
            onClick={() => onSelect(item.itemId)} />)}
          {unknown.length > 0 && <div className="clinical-chart__undated" style={{ marginTop: `${slots.length * 1.8 + .2}rem` }}>
            {unknown.map(({ item }, index) => <button type="button" key={item.itemId} aria-pressed={selectedId === item.itemId}
              aria-label={`${title(item)}，日期未明确${unknown.length > 1 ? `，记录${index + 1}` : ""}`}
              title={valueText(item) || title(item)}
              onClick={() => onSelect(item.itemId)}>{valueText(item) && valueText(item) !== title(item) ? valueText(item) : "查看记录"}{unknown.length > 1 ? ` · ${index + 1}` : ""}</button>)}
          </div>}
        </div>
      </div>;
      });
      return dated ? <div key="dated">{content}</div> : group.length > 0 && <details key="undated" className="clinical-chart__unscheduled" open={timed.length === 0}>
        <summary>日期未明确 · {group.reduce((sum, [, records]) => sum + records.length, 0)} 条记录</summary>{content}
      </details>;
    })}
    {items.length === 0 && <p className="clinical-chart__empty">暂无已整理的{label}记录。</p>}
  </section>;
}

export function ProfileTimeline({ model, onOpenEvidence, onRequestCorrection }: {
  model: PatientProfileModel;
  onOpenEvidence?: (item: ProfileItemView) => void;
  onRequestCorrection?: (item: ProfileItemView) => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const records = useMemo(() => clinicalDisplayLanes(model).flatMap(lane => lane.items).filter(item =>
    item.kind === "fact" || item.kind === "event" || item.kind === "exposure"), [model]);
  const clinical = records.filter(item => item.polarity !== "negated" && item.value !== false);
  const history = clinical.filter(item => historyLanes.includes(item.lane));
  const treatment = clinical.filter(item => treatmentLanes.includes(item.lane));
  const abnormalIds = new Set(model.highlights.filter(item => item.reasons.some(reason =>
    reason === "source_report_abnormal" || reason === "source_report_critical")).map(item => item.itemId));
  const abnormal = records.filter(item => item.referenceAbnormality || abnormalIds.has(item.itemId));
  const selected = selectedId ? model.itemById.get(selectedId) ?? null : null;
  return <section className={`clinical-journey${selected ? " clinical-journey--detail" : ""}`} aria-label="临床时间线">
    <div className="clinical-journey__charts">
      <h3 className="clinical-journey__title">临床时间线</h3>
      <ClinicalChart label="病史与诊断" tone="history" items={history} selectedId={selectedId} onSelect={setSelectedId} />
      <ClinicalChart label="用药与治疗" tone="treatment" items={treatment} selectedId={selectedId} onSelect={setSelectedId} />
      <section className="clinical-chart" aria-label="异常检验与检查"><header className="clinical-chart__head"><h3>异常检验与检查</h3></header>
        {abnormal.length === 0 ? <p className="clinical-chart__empty">暂无已标明的异常记录。</p> : <ul className="clinical-journey__abnormal">{abnormal.map(item => <li key={item.itemId}>
          <button type="button" aria-pressed={selectedId === item.itemId} onClick={() => setSelectedId(item.itemId)}>
            <strong>{title(item)}</strong><span>{valueText(item)}</span>
            {item.referenceAbnormality && <span className="clinical-journey__abnormal-value">{item.referenceAbnormality === "high" ? <ArrowUp size={16} /> : <ArrowDown size={16} />}{item.referenceAbnormality === "high" ? "高于参考上限" : "低于参考下限"}</span>}
            {!item.referenceAbnormality && <span className="clinical-journey__abnormal-value">{model.highlights.find(value => value.itemId === item.itemId)?.reasonLabels.join(" · ")}</span>}
            <span>{timelineTime(item).label}</span>
          </button>
        </li>)}</ul>}
      </section>
    </div>
    {selected && <aside className="clinical-journey__detail" aria-label="临床记录详情" id={`profile-item-${selected.itemId}`}>
      <header><h3>记录详情</h3><button type="button" className="icon-button" aria-label="关闭记录详情" title="关闭记录详情" onClick={() => setSelectedId(null)}><X size={18} /></button></header>
      <ProfileItemCard model={model} item={selected} onOpenEvidence={onOpenEvidence} onRequestCorrection={onRequestCorrection} />
    </aside>}
  </section>;
}
