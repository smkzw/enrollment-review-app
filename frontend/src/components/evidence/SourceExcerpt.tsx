/** Literal emphasis only: never rewrites the source or determines clinical truth. */
export function sharedExcerptTerms(text: string, context: string): string[] {
  if (!context) return [];
  const terms = new Set<string>();
  let previous = new Uint16Array(context.length + 1);
  for (let i = 0; i < text.length; i++) {
    const next = new Uint16Array(context.length + 1);
    for (let j = 0; j < context.length; j++) {
      if (text[i] !== context[j] || !/[\p{L}\p{N}]/u.test(text[i]!)) continue;
      const length = previous[j]! + 1;
      next[j + 1] = length;
      if (length >= 3 && (text[i + 1] !== context[j + 1] || i + 1 === text.length)) {
        const term = text.slice(i + 1 - length, i + 1);
        if (/\p{L}/u.test(term) && !/^(本研究|受试者|研究者|筛选期|基线期|临床试验|包括但不限于|研究期间)$/.test(term)) terms.add(term);
      }
    }
    previous = next;
  }
  return [...terms].sort((a, b) => b.length - a.length).filter((term, index, all) =>
    !all.slice(0, index).some(longer => longer.includes(term)));
}

export function SourceExcerpt({ text, focusTexts = [], context = "" }: {
  text: string;
  focusTexts?: readonly string[];
  context?: string;
}) {
  const terms = [...new Set([...focusTexts.filter(term => term.trim().length >= 2), ...sharedExcerptTerms(text, context)])];
  const ranges: [number, number][] = [];
  for (const term of terms) {
    for (let start = text.indexOf(term); start !== -1; start = text.indexOf(term, start + Math.max(1, term.length))) {
      if (/^[A-Za-z]+$/.test(term) && (/[A-Za-z]/.test(text[start - 1] ?? "") || /[A-Za-z]/.test(text[start + term.length] ?? ""))) continue;
      ranges.push([start, start + term.length]);
    }
  }
  const merged: [number, number][] = [];
  for (const range of ranges.sort((a, b) => a[0] - b[0])) {
    const prior = merged.at(-1);
    if (prior && range[0] <= prior[1]) prior[1] = Math.max(prior[1], range[1]);
    else merged.push([...range]);
  }
  let cursor = 0;
  return <>{merged.map(([start, end]) => {
    const before = text.slice(cursor, start); cursor = end;
    return <span key={`${start}:${end}`}>{before}<mark className="source-text-focus">{text.slice(start, end)}</mark></span>;
  })}{text.slice(cursor)}</>;
}
