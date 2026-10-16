/** Presentation only: complete sentences remain reachable, never summarized. */
export function ReasonText({ text, compact = false }: { text: string; compact?: boolean }) {
  const split = (value: string) => value.split(/(?<=；)|(?<=。)|\n+/u).filter(part => part.trim() && part.trim() !== "；");
  const parts = split(text);
  const boundary = text.search(/[。\n]/u);
  const firstSentenceEnd = boundary < 0 ? text.length : boundary + 1;
  const folded = compact && parts.length > 2 && firstSentenceEnd < text.trimEnd().length;
  const lines = (values: string[]) => <ul className="eligibility-reason-lines">{values.map((part, index) => {
    const colon = part.indexOf("：");
    return <li key={index}>{colon > 0 && colon < 64
      ? <><strong>{part.slice(0, colon + 1)}</strong>{part.slice(colon + 1)}</> : part}</li>;
  })}</ul>;
  return <>{lines(folded ? split(text.slice(0, firstSentenceEnd)) : parts)}{folded && <details key={text} className="eligibility-reason-details">
    <summary>展开核对说明</summary>{lines(split(text.slice(firstSentenceEnd)))}
  </details>}</>;
}
