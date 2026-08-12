/**
 * 来源资料类型与来源方中文显示映射。
 * fixture/v1 中的 wire 值为内部词（screening_record / investigator 等），
 * 可见文案必须使用临床工作语言（spec: quality-guidelines forbidden patterns）。
 */

const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  screening_record: "筛选记录",
  identity_record: "身份资料",
  medical_history_record: "既往病历",
  laboratory_report: "检验报告",
  medication_record: "用药记录",
  consent_record: "知情同意记录",
  other: "其他资料",
};

const SOURCE_PARTY_LABELS: Record<string, string> = {
  investigator: "研究者方",
  crc: "CRC",
  cra: "CRA",
  sponsor_medical_or_project: "申办方医学或项目组",
};

/** 资料类型中文显示；未知类型回退原文（fixture 当前仅含已登记值） */
export function documentTypeLabel(documentType: string): string {
  return DOCUMENT_TYPE_LABELS[documentType] ?? documentType;
}

/** 来源方中文显示；未知来源回退原文 */
export function sourcePartyLabel(sourceParty: string): string {
  return SOURCE_PARTY_LABELS[sourceParty] ?? sourceParty;
}
