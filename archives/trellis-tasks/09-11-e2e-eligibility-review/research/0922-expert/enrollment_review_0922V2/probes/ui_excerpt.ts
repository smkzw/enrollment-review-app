// 0922V2: copied function body from EligibilityWorkbenchPage.tsx, synthetic supporting types.
// Not a build of the user's complete frontend.
type IssueSeverity = "danger" | "attention" | "info";
type EligibilityDecision = "professional_judgment" | "indeterminate" | "exclusion_triggered" | "inclusion_met";
interface EligibilityClauseView { ruleComponentId: string; decision: EligibilityDecision; gapType: string | null; }
interface EligibilityIssueGroup { key: string; label: string; severity: IssueSeverity; clauses: EligibilityClauseView[]; }
const ISSUE_SEVERITY_ORDER: Record<IssueSeverity, number> = { danger: 0, attention: 1, info: 2 };
function decisionTone(d: EligibilityDecision) { return d === "exclusion_triggered" ? "danger" : d === "inclusion_met" ? "ok" : "info"; }
function clauseIsIssue(c: EligibilityClauseView) { return ["danger", "info"].includes(decisionTone(c.decision)); }
function clauseIssueKey(c: EligibilityClauseView): {key:string;severity:IssueSeverity} {
  return { key: c.gapType ?? "unclassified", severity: c.decision === "exclusion_triggered" ? "danger" : c.decision === "professional_judgment" ? "attention" : "info" };
}
function issueGroupLabel(k:string) { return k; }
export function buildEligibilityIssueGroups(
  clauses: ReadonlyArray<EligibilityClauseView>,
): EligibilityIssueGroup[] {
  const severities: IssueSeverity[] = ["danger", "attention", "info"];
  const severityOf = (decision: EligibilityDecision): IssueSeverity => {
    const tone = decisionTone(decision);
    if (decision === "professional_judgment") return "attention";
    return tone === "danger" ? "danger" : "info";
  };
  const byKey = new Map<string, EligibilityIssueGroup>();
  for (const clause of clauses) {
    if (!clauseIsIssue(clause)) continue;
    const { key, severity } = clauseIssueKey(clause);
    let group = byKey.get(key);
    if (!group) {
      group = { key, label: issueGroupLabel(key), severity, clauses: [] };
      byKey.set(key, group);
    } else if (
      severities.indexOf(severity) < severities.indexOf(group.severity)
    ) {
      group.severity = severity;
    }
    group.clauses.push(clause);
  }
  return [...byKey.values()].sort(
    (a, b) =>
      ISSUE_SEVERITY_ORDER[a.severity] - ISSUE_SEVERITY_ORDER[b.severity] ||
      b.clauses.length - a.clauses.length ||
      a.key.localeCompare(b.key),
  );
}
const low: EligibilityClauseView = {ruleComponentId:"low", decision:"indeterminate", gapType:"same_gap"};
const high: EligibilityClauseView = {ruleComponentId:"high", decision:"exclusion_triggered", gapType:"same_gap"};
const first = buildEligibilityIssueGroups([low, high])[0];
const reversed = buildEligibilityIssueGroups([high, low])[0];
console.log(JSON.stringify({group_severity:first.severity,default_selected:first.clauses[0].ruleComponentId,reversed_selected:reversed.clauses[0].ruleComponentId}));
