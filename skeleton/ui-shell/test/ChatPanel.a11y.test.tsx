import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { ChatPanel } from "../src/components/ChatPanel";
import type { AnswerResult } from "../src/types";

// Validates: Requirements 6.14
const result: AnswerResult = {
  snapshot_id: "snap-123",
  status: "answered",
  claims: [
    {
      kind: "fact",
      text: "Verified fact text",
      citations: [{ file: "a.ts", line_start: 1, line_end: 3 }],
      figures: [],
    },
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

describe("ChatPanel accessibility (R6.14)", () => {
  it("is a polite live log region", () => {
    render(<ChatPanel result={result} />);
    const log = screen.getByRole("log");
    expect(log.getAttribute("aria-live")).toBe("polite");
  });

  it("makes citations keyboard-reachable", () => {
    render(<ChatPanel result={result} />);
    const c = screen.getByText("[a.ts:1-3]");
    expect(c.tabIndex).toBe(0);
    c.focus();
    expect(document.activeElement).toBe(c);
  });

  it("conveys banishment as text, not only strikethrough", () => {
    render(<ChatPanel result={result} />);
    expect(screen.getByText("BANISHED")).toBeTruthy();
    expect(screen.getByText("No citation given")).toBeTruthy();
  });

  it("has no axe violations", async () => {
    const { container } = render(<ChatPanel result={result} licence="MIT" />);
    expect((await axe(container)).violations).toEqual([]);
  });
});
