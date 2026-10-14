import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FileSearch } from "lucide-react";
import type { ProfileItemView, ProfileLaneWire } from "../../api/patient-profile";
import { clinicalDisplayLanes, locatorsForItem, profileDateRoleLabel, type PatientProfileModel } from "../../features/patient-profile/model";
import { ProfileItemCard } from "./ProfileItemCard";

const categories: { id: string; label: string; lanes: readonly ProfileLaneWire[] }[] = [
  { id: "disease", label: "研究疾病与症状", lanes: ["target_disease", "symptoms_signs"] },
  { id: "history", label: "合并疾病与相关病史", lanes: ["medical_history", "allergy_infection_immune", "special_history"] },
  { id: "treatment", label: "用药与治疗", lanes: ["medication", "non_drug_treatment"] },
  { id: "exam", label: "检验、检查与评分", lanes: ["test_exam_score"] },
  { id: "study", label: "研究节点", lanes: ["study_milestone"] },
  { id: "background", label: "基本情况与其他记录", lanes: ["demographics", "reproductive", "social_environmental", "evidence_quality"] },
];
const clinicalLanes = categories.filter(value => value.id !== "background").flatMap(value => value.lanes);

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

export function ProfileTimeline({ model, onOpenEvidence, onRequestCorrection }: {
  model: PatientProfileModel;
  onOpenEvidence?: (item: ProfileItemView) => void;
  onRequestCorrection?: (item: ProfileItemView) => void;
}) {
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());
  const lanes = useMemo(() => clinicalDisplayLanes(model), [model]);
  const records = useMemo(() => lanes.flatMap(lane => lane.items).filter(item =>
    item.kind === "fact" || item.kind === "event" || item.kind === "exposure"), [lanes]);
  const clinicalIds = useMemo(() => {
    const highlighted = new Set(model.highlights.filter(item => item.reasons.some(reason =>
      reason !== "structured_ocr_or_parse_risk")).map(item => item.itemId));
    return new Set(records.filter(item => clinicalLanes.includes(item.lane) || highlighted.has(item.itemId)).map(item => item.itemId));
  }, [model.highlights, records]);
  const clinicalCount = clinicalIds.size;
  const [category, setCategory] = useState(clinicalCount > 0 ? "clinical" : "all");
  const groups = useMemo(() => {
    const selected = categories.find(value => value.id === category);
    const values = new Map<string, { label: string; role: string | null; sort: string | null; items: ProfileItemView[] }>();
    for (const item of records) {
      if (selected && !selected.lanes.includes(item.lane)) continue;
      if (category === "clinical" && !clinicalIds.has(item.itemId)) continue;
      const time = timelineTime(item);
      const group = values.get(time.key) ?? { ...time, items: [] };
      group.items.push(item);
      values.set(time.key, group);
    }
    return [...values.entries()].sort(([keyA, a], [keyB, b]) =>
      keyA === "unknown" ? keyB === "unknown" ? 0 : 1 : keyB === "unknown" ? -1
        : a.sort === null ? b.sort === null ? 0 : 1 : b.sort === null ? -1 : a.sort.localeCompare(b.sort));
  }, [category, clinicalIds, records]);
  const toggle = (id: string) => setExpanded(previous => {
    const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next;
  });
  return <section className="profile-timeline" aria-label="临床时间线">
    <header className="profile-timeline__head"><h3>临床时间线</h3></header>
    <div className="profile-timeline__categories" role="group" aria-label="时间线分类">
      {clinicalCount > 0 && <button type="button" aria-pressed={category === "clinical"} onClick={() => setCategory("clinical")}>病史与诊疗 {clinicalCount}</button>}
      <button type="button" aria-pressed={category === "all"} onClick={() => setCategory("all")}>全部 {records.length}</button>
      {categories.map(value => {
        const count = records.filter(item => value.lanes.includes(item.lane)).length;
        return <button type="button" key={value.id} aria-pressed={category === value.id}
          onClick={() => setCategory(value.id)}>{value.label} {count}</button>;
      })}
    </div>
    <ol className="profile-timeline__groups">
      {groups.map(([key, group]) => <li key={key} className="profile-timeline__group">
        <div className="profile-timeline__date"><h4>{group.label}</h4>{group.role && <span>{group.role}</span>}</div>
        <ul>{group.items.map(item => {
          const locators = locatorsForItem(model, item);
          const isOpen = expanded.has(item.itemId);
          const value = item.value === null ? null : typeof item.value === "boolean"
            ? item.value ? item.polarity === "negated" ? "明确否认" : item.polarity === "unknown" ? "未明确" : "有记录" : "否"
            : String(item.value);
          const detail = item.kind === "exposure" ? item.subtitle : null;
          const highlight = model.highlights.find(value => value.itemId === item.itemId);
          return <li key={item.itemId} id={`profile-item-${item.itemId}`} className="profile-timeline__record">
            <button type="button" className="profile-timeline__open" aria-expanded={isOpen}
              aria-controls={`timeline-detail-${item.itemId}`} onClick={() => toggle(item.itemId)}>
              {isOpen ? <ChevronDown size={17} aria-hidden="true" /> : <ChevronRight size={17} aria-hidden="true" />}
              <span className="profile-timeline__record-content">
                <span className="profile-timeline__record-head"><strong>{item.title}</strong>
                  {value !== null && <span className="profile-timeline__value">{value}{item.unit && item.unit !== "unitless" ? ` ${item.unit}` : ""}</span>}
                  <span className="profile-timeline__category">{item.laneLabel}</span>
                </span>
                {detail && <span>{detail}</span>}
                {highlight && <span className="profile-timeline__attention">{highlight.reasonLabels.join(" · ")}</span>}
              </span>
            </button>
            {onOpenEvidence && locators.length > 0 && <button type="button" className="icon-button profile-timeline__source"
              title={`查看原件第${locators[0].pageNumber}页`} aria-label={`查看${item.title}原件`} onClick={() => onOpenEvidence(item)}>
              <FileSearch size={18} aria-hidden="true" />
            </button>}
            {isOpen && <div className="profile-timeline__details" id={`timeline-detail-${item.itemId}`}>
              <ProfileItemCard model={model} item={item} onOpenEvidence={onOpenEvidence} onRequestCorrection={onRequestCorrection} />
            </div>}
          </li>;
        })}</ul>
      </li>)}
    </ol>
    {groups.length === 0 && <p>此类暂无已整理的临床记录。</p>}
  </section>;
}
