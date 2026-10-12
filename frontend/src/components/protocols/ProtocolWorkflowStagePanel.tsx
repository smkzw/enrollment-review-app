import { useState } from "react";
import { getProtocolWorkbenchRepository } from "../../api/protocolWorkbenchRepository";
import type { DraftRevisionView } from "../../api/protocolWorkbenchTypes";

const stages = { pre_screening: "预筛", screening: "筛选", run_in: "导入／洗脱", baseline: "基线" };
type Stage = keyof typeof stages;
const record = (value: unknown): Record<string, unknown> | null =>
  value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;

export function setReviewedStage(content: Record<string, unknown>, id: string, stage: Stage) {
  const next = structuredClone(content);
  const rows = Array.isArray(next.proposed_workflow_stages) ? next.proposed_workflow_stages.map(record) : [];
  const target = rows.find(row => row?.workflow_stage_id === id);
  if (!target || !Array.isArray(target.due_requirement_ids)) throw new Error("该节点的资料要求无法对应，请刷新后核对。");
  const oldStage = target.stage;
  const ids = new Set(target.due_requirement_ids);
  target.stage = stage;
  // The original visit text and identities stay unchanged; only this node's linked due-stage is edited.
  const changeRequirements = (value: unknown) => {
    const component = record(value);
    if (!component || !Array.isArray(component.evidence_requirements)) return;
    for (const value of component.evidence_requirements) {
      const requirement = record(value);
      if (requirement && ids.has(requirement.requirement_id) && requirement.due_stage === oldStage) requirement.due_stage = stage;
    }
  };
  for (const value of Array.isArray(next.proposed_rules) ? next.proposed_rules : []) {
    const rule = record(value);
    for (const component of Array.isArray(rule?.components) ? rule.components : []) changeRequirements(component);
  }
  for (const value of Array.isArray(next.component_drafts) ? next.component_drafts : []) changeRequirements(record(value)?.proposed_component);
  for (const value of Array.isArray(next.evidence_requirement_drafts) ? next.evidence_requirement_drafts : []) {
    const requirement = record(record(value)?.proposed_requirement);
    if (requirement && ids.has(requirement.requirement_id) && requirement.due_stage === oldStage) requirement.due_stage = stage;
  }
  return next;
}

export function ProtocolWorkflowStagePanel({ jobId, draft, onSaved }: {
  jobId: string; draft: Pick<DraftRevisionView, "content" | "revisionId">; onSaved: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rows = Array.isArray(draft.content.proposed_workflow_stages) ? draft.content.proposed_workflow_stages.map(record) : [];
  async function save(id: string, stage: Stage) {
    setBusy(true); setError(null);
    try {
      await getProtocolWorkbenchRepository().editDraft(jobId, {
        expectedRevisionId: draft.revisionId, draft: setReviewedStage(draft.content, id, stage),
        reviewedStageAssignment: true,
      });
      onSaved();
    } catch (error) { setError(error instanceof Error ? error.message : "审核节点未能保存。"); }
    finally { setBusy(false); }
  }
  return <section aria-label="审核节点核对">
    <h2>审核节点</h2>
    {error && <p role="alert">{error}</p>}
    {rows.map(row => row && typeof row.workflow_stage_id === "string" && typeof row.stage === "string"
      && row.stage in stages && <label key={row.workflow_stage_id}>
        {String(row.display_name)} · {String(row.visit_instance ?? "")}
        <select aria-label={`${String(row.display_name)}所属阶段`} disabled={busy} value={row.stage}
          onChange={event => void save(String(row.workflow_stage_id), event.target.value as Stage)}>
          {Object.entries(stages).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
      </label>)}
  </section>;
}
