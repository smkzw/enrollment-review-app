// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { identityReviewFixture } from "../../fixtures/protocol-deconstruction-workbench";
import { ProtocolIdentityPanel } from "./ProtocolIdentityPanel";

describe("方案身份确认", () => {
  it("识别缺少版本日期时允许补录并按日精度提交", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <ProtocolIdentityPanel
        review={{
          ...identityReviewFixture,
          identity: {
            ...identityReviewFixture.identity,
            officialDateValue: null,
            officialDatePrecision: null,
          },
        }}
        busy={false}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("来源摘录：II期临床试验")).toBeInTheDocument();
    expect(screen.getByText("来源摘录：III 期（页眉模板）")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "确认并继续解构" });
    expect(confirm).toBeDisabled();
    const dateInput = screen.getByRole("textbox", { name: /版本日期/ });
    await user.type(dateInput, "2026-02-30");
    expect(confirm).toBeDisabled();
    expect(dateInput).toHaveAttribute("aria-invalid", "true");
    await user.clear(dateInput);
    await user.type(dateInput, "0000");
    expect(confirm).toBeDisabled();
    expect(dateInput).toHaveAttribute("aria-invalid", "true");
    await user.clear(dateInput);
    await user.type(dateInput, "0000-01");
    expect(confirm).toBeDisabled();
    expect(dateInput).toHaveAttribute("aria-invalid", "true");
    await user.clear(dateInput);
    await user.type(dateInput, "2026-08-17");
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        officialDateValue: "2026-08-17",
        officialDatePrecision: "day",
        studyPhase: "phase_ii",
      }),
    );
  });

  it("展示来源候选并允许选择冲突值回填身份字段", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <ProtocolIdentityPanel
        review={{
          ...identityReviewFixture,
          identity: {
            ...identityReviewFixture.identity,
            protocolCode: null,
            selectedCandidateIds: [],
          },
          metadataCandidates: [
            {
              candidateId: "code-a",
              field: "protocol_code",
              fieldLabel: "方案编号",
              value: "PROTO-A",
              sourceLabel: "方案首页",
              sourceExcerpt: "方案编号：PROTO-A",
              isFallback: false,
            },
            {
              candidateId: "code-b",
              field: "protocol_code",
              fieldLabel: "方案编号",
              value: "PROTO-B",
              sourceLabel: "页眉或页脚",
              sourceExcerpt: "Protocol No.: PROTO-B",
              isFallback: false,
            },
          ],
          metadataConflicts: [
            {
              conflictId: "conflict-code",
              field: "protocol_code",
              fieldLabel: "方案编号",
              reason: "首页与页眉的方案编号不一致。",
              candidates: [
                { candidateId: "code-a", value: "PROTO-A", sourceLabel: "方案首页" },
                { candidateId: "code-b", value: "PROTO-B", sourceLabel: "页眉或页脚" },
              ],
            },
          ],
        }}
        busy={false}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getAllByText("方案编号：PROTO-A").length).toBeGreaterThan(0);
    const candidate = screen.getByRole("radio", { name: /PROTO-B/ });
    await user.click(candidate);
    expect(screen.getByRole("textbox", { name: /方案编号/ })).toHaveValue("PROTO-B");
    await user.click(screen.getByRole("button", { name: "确认并继续解构" }));

    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({
        protocolCode: "PROTO-B",
        selectedCandidateIds: ["code-b"],
      }),
    );
  });
});
