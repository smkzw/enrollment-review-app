import { expect, it } from "vitest";
import { setReviewedStage } from "./ProtocolWorkflowStagePanel";

it("节点选择只改变明确关联要求的阶段，保留原访视文字、定义和兄弟", () => {
  const selected = { requirement_id: "req-a", due_stage: "run_in", variable_id: "age" };
  const sibling = { requirement_id: "req-b", due_stage: "run_in", variable_id: "age" };
  const input = {
    proposed_workflow_stages: [
      { workflow_stage_id: "node-a", stage: "run_in", visit_instance: "筛选/导入期 V1", due_requirement_ids: ["req-a"] },
      { workflow_stage_id: "node-b", stage: "run_in", due_requirement_ids: ["req-b"] },
    ],
    proposed_rules: [{ components: [{ evidence_requirements: [selected, sibling] }] }],
    component_drafts: [{ proposed_component: { evidence_requirements: [selected] } }],
    evidence_requirement_drafts: [{ proposed_requirement: selected }, { proposed_requirement: sibling }],
  };
  const next = setReviewedStage(input, "node-a", "screening") as typeof input;
  expect(next.proposed_workflow_stages[0]).toEqual({ ...input.proposed_workflow_stages[0], stage: "screening" });
  expect(next.proposed_workflow_stages[1]).toEqual(input.proposed_workflow_stages[1]);
  expect(next.proposed_rules[0].components[0].evidence_requirements).toEqual([{ ...selected, due_stage: "screening" }, sibling]);
  expect(next.component_drafts[0].proposed_component.evidence_requirements[0].due_stage).toBe("screening");
  expect(next.evidence_requirement_drafts[0].proposed_requirement.due_stage).toBe("screening");
  expect(input.proposed_rules[0].components[0].evidence_requirements[0].due_stage).toBe("run_in");
  expect(() => setReviewedStage(input, "other", "baseline")).toThrow();
});
