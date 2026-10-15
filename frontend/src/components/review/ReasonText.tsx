/** Presentation only: complete sentences remain reachable, never summarized. */
export function ReasonText({ text, compact = false }: { text: string; compact?: boolean }) {
  const parts = text.split(/(?<=；)|(?<=。)|\n+/u).filter(part => part.trim() && part.trim() !== "；");
  const folded = compact && parts.length > 2;
  const lines = (values: string[]) => <ul className="eligibility-reason-lines">{values.map((part, index) => {
    const colon = part.indexOf("：");
    return <li key={index}>{colon > 0 && colon < 64
      ? <><strong>{part.slice(0, colon + 1)}</strong>{part.slice(colon + 1)}</> : part}</li>;
  })}</ul>;
  return <>{lines(folded ? parts.slice(0, 1) : parts)}{folded && <details key={text} className="eligibility-reason-details">
    <summary>展开核对说明</summary>{lines(parts.slice(1))}
  </details>}</>;
}
