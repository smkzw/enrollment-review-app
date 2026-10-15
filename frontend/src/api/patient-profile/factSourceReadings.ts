import type { ProfileScalarValue } from "./patientProfileViewModels";

export interface FactSourceReadingView {
  candidateId: string;
  rawValue: ProfileScalarValue | null;
  canonicalValue: ProfileScalarValue | null;
  unit: string | null;
  sourceDateText: string | null;
  locatorIds: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function decodeFactSourceReadings(payload: unknown): FactSourceReadingView[] {
  if (!Array.isArray(payload)) throw new Error("来源读数格式不正确");
  return payload.map((entry: unknown) => {
    if (!isRecord(entry)) {
      throw new Error("来源读数格式不正确");
    }
    const row = entry;
    const scalar = (value: unknown): value is ProfileScalarValue | null =>
      value === null || typeof value === "string" || typeof value === "boolean" ||
      (typeof value === "number" && Number.isFinite(value));
    if (typeof row.candidate_id !== "string" || !row.candidate_id ||
        !scalar(row.raw_value) || !scalar(row.canonical_value) ||
        !(row.unit === null || typeof row.unit === "string") ||
        !(row.source_date_text === null || typeof row.source_date_text === "string") ||
        !Array.isArray(row.locator_ids) ||
        !row.locator_ids.every((id: unknown) => typeof id === "string" && id.length > 0)) {
      throw new Error("来源读数格式不正确");
    }
    return {
      candidateId: row.candidate_id,
      rawValue: row.raw_value,
      canonicalValue: row.canonical_value,
      unit: row.unit,
      sourceDateText: row.source_date_text,
      locatorIds: row.locator_ids,
    };
  });
}
