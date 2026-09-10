/**
 * 人工事实修订的中文显示组件：只把临床语义投影给监查员，隐藏后端字段名和机器枚举。
 */

import type { ProfileItemView } from "../../api/patient-profile";
import type {
  FactCorrectionImpactView,
  FactCorrectionJsonRecord,
  FactCorrectionJsonValue,
} from "../../api/patient-profile";
import { formatProfileDateTime } from "../../features/patient-profile/model";

export interface CorrectionSnapshotEntry {
  label: string;
  value: string;
}

function isRecord(value: FactCorrectionJsonValue | undefined): value is FactCorrectionJsonRecord {
  return value !== undefined && value !== null && typeof value === "object" && !Array.isArray(value);
}

function textValue(value: FactCorrectionJsonValue | undefined): string | null {
  if (value === undefined || value === null) return null;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return null;
}

function nullableText(value: FactCorrectionJsonValue | undefined): string {
  return textValue(value) ?? "未记录";
}

function polarityLabel(value: FactCorrectionJsonValue | undefined): string {
  switch (value) {
    case "affirmed":
      return "肯定";
    case "negated":
      return "否定";
    case "unknown":
      return "未明确";
    default:
      return "未记录";
  }
}

function durationLabel(value: FactCorrectionJsonValue | undefined): string {
  switch (value) {
    case "ongoing":
      return "持续";
    case "ended":
      return "已结束";
    case "intermittent":
      return "间歇";
    case "single":
      return "单次";
    case "unknown":
      return "未明确";
    default:
      return "未记录";
  }
}

function sourceStrengthLabel(value: FactCorrectionJsonValue | undefined): string {
  switch (value) {
    case "contemporaneous_objective_result":
      return "同期客观结果";
    case "historical_primary_document":
      return "既往原始资料";
    case "current_study_chart_direct_record":
      return "当前研究病历直接记录";
    case "screening_record_transcription":
      return "筛选病历转述";
    case "unverifiable_source":
      return "来源无法确认";
    default:
      return "未记录";
  }
}

function eventTypeLabel(value: FactCorrectionJsonValue | undefined): string {
  switch (value) {
    case "symptom":
      return "症状";
    case "diagnosis":
      return "诊断";
    case "procedure":
      return "操作或治疗";
    case "adverse_event":
      return "不良事件";
    case "hospitalization":
      return "住院事件";
    default:
      return "事件记录";
  }
}

function dateRangeText(value: FactCorrectionJsonValue | undefined): string {
  if (!isRecord(value)) return "未记录";
  const source = textValue(value.source_text) ?? "日期未记录";
  const precision = textValue(value.precision);
  const precisionText =
    precision === "day"
      ? "日"
      : precision === "month"
        ? "月"
        : precision === "year"
          ? "年"
          : precision === "unknown"
            ? "未明确精度"
            : null;
  const lower = textValue(value.lower_bound);
  const upper = textValue(value.upper_bound);
  const bounds = lower !== null || upper !== null ? ` · ${lower ?? "未知"} 至 ${upper ?? "未知"}` : "";
  return `${source}${precisionText === null ? "" : `（${precisionText}）`}${bounds}`;
}

function scalarWithUnit(value: FactCorrectionJsonValue | undefined, unit: FactCorrectionJsonValue | undefined): string {
  const scalar = nullableText(value);
  const unitText = textValue(unit);
  return unitText === null || scalar === "未记录" ? scalar : `${scalar} ${unitText}`;
}

function snapshotValue(
  snapshot: FactCorrectionJsonRecord,
  key: string,
  fallback: string,
): FactCorrectionJsonValue | undefined {
  return key in snapshot ? snapshot[key] : fallback;
}

export function correctionSnapshotEntries(
  snapshot: FactCorrectionJsonRecord,
  targetKind: "fact" | "event" | "exposure",
  item?: ProfileItemView,
): CorrectionSnapshotEntry[] {
  if (targetKind === "fact") {
    return [
      {
        label: "记录性质",
        value: polarityLabel(snapshotValue(snapshot, "polarity", item?.polarityLabel ?? "未记录")),
      },
      {
        label: "记录项目",
        value: nullableText(snapshotValue(snapshot, "asserted_object", item?.assertedObject ?? "未记录")),
      },
      {
        label: "记录结果",
        value: scalarWithUnit(snapshot.value, snapshot.unit),
      },
      {
        label: "事件时间",
        value: dateRangeText(snapshot.date_range),
      },
      {
        label: "来源强度",
        value: sourceStrengthLabel(snapshot.source_strength),
      },
    ];
  }

  if (targetKind === "event") {
    return [
      {
        label: "事件类型",
        value: eventTypeLabel(snapshot.event_type),
      },
      {
        label: "发生时间",
        value: dateRangeText(snapshot.start_range),
      },
      {
        label: "结束时间",
        value: dateRangeText(snapshot.end_range),
      },
      {
        label: "持续状态",
        value: durationLabel(snapshot.duration_status),
      },
      {
        label: "来源强度",
        value: sourceStrengthLabel(snapshot.source_strength),
      },
    ];
  }

  return [
    { label: "药物或治疗", value: nullableText(snapshot.medication_name) },
    { label: "类别", value: nullableText(snapshot.category) },
    { label: "适应证", value: nullableText(snapshot.indication) },
    { label: "剂量", value: scalarWithUnit(snapshot.dose, snapshot.unit) },
    { label: "频次", value: nullableText(snapshot.frequency) },
    { label: "途径", value: nullableText(snapshot.route) },
    { label: "开始时间", value: dateRangeText(snapshot.start_range) },
    { label: "结束时间", value: dateRangeText(snapshot.end_range) },
    { label: "持续状态", value: durationLabel(snapshot.duration_status) },
    { label: "来源强度", value: sourceStrengthLabel(snapshot.source_strength) },
  ];
}

export function CorrectionSnapshotPanel({
  label,
  snapshot,
  targetKind,
  item,
}: {
  label: string;
  snapshot: FactCorrectionJsonRecord;
  targetKind: "fact" | "event" | "exposure";
  item?: ProfileItemView;
}) {
  return (
    <section className="profile-correction-snapshot" aria-label={label}>
      <h4>{label}</h4>
      <dl>
        {correctionSnapshotEntries(snapshot, targetKind, item).map((entry) => (
          <div key={`${label}-${entry.label}`}>
            <dt>{entry.label}</dt>
            <dd>{entry.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

export function CorrectionImpactSummary({ impact }: { impact: FactCorrectionImpactView }) {
  const rows = [
    ["原文定位", impact.affectedLocatorIds.length],
    ["资料文件", impact.affectedDocumentIds.length],
    ["事实记录", impact.affectedFactIds.length],
    ["事件记录", impact.affectedEventIds.length],
    ["用药或治疗暴露", impact.affectedExposureIds.length],
    ["冲突组", impact.affectedConflictGroupIds.length],
    ["相关规则", impact.affectedRuleLinkIds.length],
    ["资料期望", impact.affectedExpectationIds.length],
    ["受影响历史档案", impact.affectedProfileRevisionIds.length],
  ] as const;
  return (
    <dl className="profile-correction-impact__counts">
      {rows.map(([label, count]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{count}</dd>
        </div>
      ))}
    </dl>
  );
}

export function correctionHistoryTime(iso: string): string {
  return formatProfileDateTime(iso) ?? "时间未记录";
}

export function correctionOperatorLabel(operatorId: string): string {
  return operatorId === "local-reviewer" ? "本机审核人员" : "审核人员";
}
