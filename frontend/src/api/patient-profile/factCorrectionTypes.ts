/**
 * Slice 5.7 人工事实修订的前端输入合同。
 * 组件只构造领域语义；HTTP 仓储负责转换为后端 snake_case 载荷。
 */

import type { ProfileDatePrecisionWire } from "./patientProfileTypes";

export type FactCorrectionTargetKind = "fact" | "event" | "exposure";

export type FactCorrectionJsonValue =
  | null
  | boolean
  | number
  | string
  | FactCorrectionJsonValue[]
  | { [key: string]: FactCorrectionJsonValue };

export interface FactCorrectionDateRangeInput {
  sourceText: string | null;
  precision: ProfileDatePrecisionWire | null;
  lowerBound: string | null;
  upperBound: string | null;
}

export interface FactCorrectionDateRangeWire {
  source_text: string | null;
  precision: ProfileDatePrecisionWire | null;
  lower_bound: string | null;
  upper_bound: string | null;
}

export interface FactCorrectionUpdates {
  factType?: string | null;
  supportedRequirementIds?: string[] | null;
  polarity?: string | null;
  assertedObject?: string | null;
  value?: FactCorrectionJsonValue;
  unit?: string | null;
  dateRange?: FactCorrectionDateRangeInput | null;
  profileLane?: string | null;
  eventType?: string | null;
  startRange?: FactCorrectionDateRangeInput | null;
  endRange?: FactCorrectionDateRangeInput | null;
  durationStatus?: string | null;
  factIds?: string[] | null;
  medicationName?: string | null;
  category?: string | null;
  indication?: string | null;
  dose?: string | null;
  frequency?: string | null;
  route?: string | null;
}

export interface FactCorrectionRequestInput {
  targetKind: FactCorrectionTargetKind;
  targetId: string;
  locatorIds: string[];
  reason: string;
  operatorId?: string;
  updates: FactCorrectionUpdates;
}

/** 只在 API 层使用的后端请求载荷；不向组件树透传。 */
export interface FactCorrectionRequestWire {
  target_kind: FactCorrectionTargetKind;
  target_id: string;
  locator_ids: string[];
  reason: string;
  operator_id?: string;
  fact_type?: string | null;
  supported_requirement_ids?: string[] | null;
  polarity?: string | null;
  asserted_object?: string | null;
  value?: FactCorrectionJsonValue;
  unit?: string | null;
  date_range?: FactCorrectionDateRangeWire | null;
  profile_lane?: string | null;
  event_type?: string | null;
  start_range?: FactCorrectionDateRangeWire | null;
  end_range?: FactCorrectionDateRangeWire | null;
  duration_status?: string | null;
  fact_ids?: string[] | null;
  medication_name?: string | null;
  category?: string | null;
  indication?: string | null;
  dose?: string | null;
  frequency?: string | null;
  route?: string | null;
}

export function encodeFactCorrectionRequest(
  input: FactCorrectionRequestInput,
): FactCorrectionRequestWire {
  const encodeDateRange = (
    value: FactCorrectionDateRangeInput | null,
  ): FactCorrectionDateRangeWire | null =>
    value === null
      ? null
      : {
          source_text: value.sourceText,
          precision: value.precision,
          lower_bound: value.lowerBound,
          upper_bound: value.upperBound,
        };
  const updates = input.updates;
  const wire: FactCorrectionRequestWire = {
    target_kind: input.targetKind,
    target_id: input.targetId,
    locator_ids: [...input.locatorIds],
    reason: input.reason,
  };
  if (input.operatorId !== undefined) wire.operator_id = input.operatorId;
  if (updates.factType !== undefined) wire.fact_type = updates.factType;
  if (updates.supportedRequirementIds !== undefined) {
    wire.supported_requirement_ids = updates.supportedRequirementIds;
  }
  if (updates.polarity !== undefined) wire.polarity = updates.polarity;
  if (updates.assertedObject !== undefined) wire.asserted_object = updates.assertedObject;
  if ("value" in updates) wire.value = updates.value;
  if (updates.unit !== undefined) wire.unit = updates.unit;
  if (updates.dateRange !== undefined) wire.date_range = encodeDateRange(updates.dateRange);
  if (updates.profileLane !== undefined) wire.profile_lane = updates.profileLane;
  if (updates.eventType !== undefined) wire.event_type = updates.eventType;
  if (updates.startRange !== undefined) wire.start_range = encodeDateRange(updates.startRange);
  if (updates.endRange !== undefined) wire.end_range = encodeDateRange(updates.endRange);
  if (updates.durationStatus !== undefined) wire.duration_status = updates.durationStatus;
  if (updates.factIds !== undefined) wire.fact_ids = updates.factIds;
  if (updates.medicationName !== undefined) wire.medication_name = updates.medicationName;
  if (updates.category !== undefined) wire.category = updates.category;
  if (updates.indication !== undefined) wire.indication = updates.indication;
  if (updates.dose !== undefined) wire.dose = updates.dose;
  if (updates.frequency !== undefined) wire.frequency = updates.frequency;
  if (updates.route !== undefined) wire.route = updates.route;
  return wire;
}
