export interface TextRange {
  textStart: number;
  textEnd: number;
}

// Presentation only: unknown or mixed clinical lines stay visible. Offsets always
// refer to the unchanged source, never to the shortened reading view.
export function administrativeLineRanges(text: string): TextRange[] {
  const ranges: TextRange[] = [];
  const clinical = /(?:^|[^A-Za-z])(?:CS|NCS|mg|mmol|[μµ]mol|mmHg|IU)(?:$|[^A-Za-z])|临床|研究者|判断|评估|诊断|症状|结果|阴性|阳性|采样|采集|检查|复查|给药|用药|治疗|异常|报告日期|检验日期|就诊|访视|出生|年龄|性别|标本|参考|单位/i;
  const administrative = /^(?:(?:检验者|检验员|检验人员|检验医师|检验医生|主检|审核|审核者|审核医师|审核医生|报告医师|报告医生|申请医师|申请医生|医师姓名|打印者|打印人员|打印时间|打印日期|地址|网址|联系(?:电话|方式)|样本号|检验仪器|唯一编号)\s*[:：]|第\s*(?:\d+|\(\s*\d+\s*\))\s*页\s*(?:[\/／·,，]?\s*共\s*\d+\s*页)?\s*$)/;
  let offset = 0;
  for (const line of text.split("\n")) {
    const normalized = line.normalize("NFKC").trim();
    if (administrative.test(normalized) && !clinical.test(normalized)) {
      ranges.push({ textStart: offset, textEnd: offset + line.length });
    }
    offset += line.length + 1;
  }
  return ranges;
}

export function clinicalReadingText(text: string): string {
  const ranges = administrativeLineRanges(text);
  let offset = 0;
  return text.split("\n").filter((line) => {
    const start = offset;
    offset += line.length + 1;
    return !ranges.some((range) => range.textStart === start);
  }).join("\n");
}

export function isAdministrativeRange(range: TextRange, ranges: TextRange[]): boolean {
  return range.textEnd > range.textStart && ranges.some((line) =>
    range.textStart >= line.textStart && range.textEnd <= line.textEnd);
}
