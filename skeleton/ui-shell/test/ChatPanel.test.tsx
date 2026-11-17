import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ChatPanel } from "../src/components/ChatPanel";
import type { AnswerResult } from "../src/types";

const base: AnswerResult = {
  snapshot_id: "snap-123",
  status: "answered",
  claims: [
    {
      kind: "fact",
      text: "Verified fact text",
      citations: [{ file: "a.ts", line_start: 1, line_end: 3 }],
      figures: [],
    },
    { kind: "guess", text: "Maybe this", citations: [], figures: [] },
  ],
  banishments: [
    {
      claim_text: "Invented claim",
      reason: "uncited_claim",
      message: "No citation given",
      attempt: 1,
      snapshot_id: "snap-123",
    },
  ],
  decline_line: null,
  attempts: [],
};

describe("ChatPanel", () => {
  it("renders claims with citations and a visible guess label", () => {
    render(<ChatPanel result={base} />);
    expect(screen.getByText(/Verified fact text/)).toBeTruthy();
    expect(screen.getByText("[a.ts:1-3]")).toBeTruthy();
    expect(screen.getByText("guess")).toBeTruthy();
  });

  it("keeps banished claim text inside the banishment block only", () => {
    const { container } = render(<ChatPanel result={base} />);
    const block = screen.getByTestId("banishment");
    expect(within(block).getByText("BANISHED")).toBeTruthy();
    expect(block.querySelector("del")?.textContent).toBe("Invented claim");
    expect(within(block).getByText("No citation given")).toBeTruthy();
    expect(container.textContent?.split("Invented claim").length).toBe(2);
    expect(container.querySelectorAll("del")).toHaveLength(1);
  });

  it("shows only banishments and the decline line when declined", () => {
    render(
      <ChatPanel
        result={{ ...base, status: "declined", decline_line: "I cannot answer that." }}
      />,
    );
    expect(screen.queryByText(/Verified fact text/)).toBeNull();
    expect(screen.queryByText("guess")).toBeNull();
    expect(screen.getAllByTestId("banishment")).toHaveLength(1);
    expect(screen.getByTestId("decline-line").textContent).toBe("I cannot answer that.");
  });

  it("shows the Snapshot ID and the licence when passed", () => {
    const { rerender } = render(<ChatPanel result={base} />);
    expect(screen.getByText(/Snapshot ID: snap-123/)).toBeTruthy();
    expect(screen.queryByText(/Licence/)).toBeNull();
    rerender(<ChatPanel result={base} licence="MIT" />);
    expect(screen.getByText(/Licence: MIT/)).toBeTruthy();
  });
});
