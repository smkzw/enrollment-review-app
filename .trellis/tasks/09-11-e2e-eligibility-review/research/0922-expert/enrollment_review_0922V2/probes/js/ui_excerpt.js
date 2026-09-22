"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.buildEligibilityIssueGroups = buildEligibilityIssueGroups;
const ISSUE_SEVERITY_ORDER = { danger: 0, attention: 1, info: 2 };
function decisionTone(d) { return d === "exclusion_triggered" ? "danger" : d === "inclusion_met" ? "ok" : "info"; }
function clauseIsIssue(c) { return ["danger", "info"].includes(decisionTone(c.decision)); }
function clauseIssueKey(c) {
    return { key: c.gapType ?? "unclassified", severity: c.decision === "exclusion_triggered" ? "danger" : c.decision === "professional_judgment" ? "attention" : "info" };
}
function issueGroupLabel(k) { return k; }
function buildEligibilityIssueGroups(clauses) {
    const severities = ["danger", "attention", "info"];
    const severityOf = (decision) => {
        const tone = decisionTone(decision);
        if (decision === "professional_judgment")
            return "attention";
        return tone === "danger" ? "danger" : "info";
    };
    const byKey = new Map();
    for (const clause of clauses) {
        if (!clauseIsIssue(clause))
            continue;
        const { key, severity } = clauseIssueKey(clause);
        let group = byKey.get(key);
        if (!group) {
            group = { key, label: issueGroupLabel(key), severity, clauses: [] };
            byKey.set(key, group);
        }
        else if (severities.indexOf(severity) < severities.indexOf(group.severity)) {
            group.severity = severity;
        }
        group.clauses.push(clause);
    }
    return [...byKey.values()].sort((a, b) => ISSUE_SEVERITY_ORDER[a.severity] - ISSUE_SEVERITY_ORDER[b.severity] ||
        b.clauses.length - a.clauses.length ||
        a.key.localeCompare(b.key));
}
const low = { ruleComponentId: "low", decision: "indeterminate", gapType: "same_gap" };
const high = { ruleComponentId: "high", decision: "exclusion_triggered", gapType: "same_gap" };
const first = buildEligibilityIssueGroups([low, high])[0];
const reversed = buildEligibilityIssueGroups([high, low])[0];
console.log(JSON.stringify({ group_severity: first.severity, default_selected: first.clauses[0].ruleComponentId, reversed_selected: reversed.clauses[0].ruleComponentId }));
