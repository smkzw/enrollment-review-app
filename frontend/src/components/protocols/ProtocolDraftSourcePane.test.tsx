// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProtocolDraftSourcePane } from "./ProtocolDraftSourcePane";
import type { ProtocolSourceLocatorView } from "../../domain/protocolViewModels";

describe("方案原文展示", () => {
  it("同页只列一次位置标题，原文不同位置与限定语全部保留", () => {
    const location: ProtocolSourceLocatorView = { sourceSpanId: "a", sourceRef: "方案正文", pageLabel: "第 3 页",
      excerpt: "条件A且不符合例外", precision: "text_range", precisionLabel: "文本范围", degradationReason: null };
    render(<ProtocolDraftSourcePane component={null} fileName="方案" selectionLabel="IN-01"
      locators={[location, { ...location, sourceSpanId: "b", excerpt: "条件B或者条件C" },
        { ...location, sourceSpanId: "c", pageLabel: "第 4 页", excerpt: "条件A且不符合例外" }]} />);
    expect(screen.getAllByText("第 3 页")).toHaveLength(1);
    expect(screen.getAllByText("条件A且不符合例外")).toHaveLength(2);
    expect(screen.getByText("条件B或者条件C")).toBeInTheDocument();
    expect(screen.getByText("第 4 页")).toBeInTheDocument();
  });
});
