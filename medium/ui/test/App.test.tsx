import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { App } from "../src/App";
import type { AnswerResult } from "../src/types";

const REF = "snap-1";

const answered: AnswerResult = {
  snapshot_id: REF,
  status: "answered",
  claims: [
    {
      kind: "fact",
      text: "This module has not moved in a long while.",
      citations: [{ file: "src/pkg/mod.py", line_start: 3, line_end: 9 }],
      figures: [],
    },
    { kind: "guess", text: "I suspect a leap year is to blame.", citations: [], figures: [] },
  ],
  banishments: [
    {
      claim_text: "It was written by a fool.",
      reason: "uncited_claim",
      message: "The claim carried no citation.",
      attempt: 1,
      snapshot_id: REF,
    },
  ],
  decline_line: null,
  attempts: [],
};

const declined: AnswerResult = {
  snapshot_id: REF,
  status: "declined",
  claims: [],
  banishments: [],
  decline_line: "The spirits are silent on that.",
  attempts: [],
};

const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status });

/** Routes fetch by URL; `asks` are returned in order from the ask endpoint. */
function mockApi(asks: Array<AnswerResult | { status: number; body: unknown }>) {
  let n = 0;
  const fn = vi.fn(async (url: string, _init?: RequestInit) => {
    if (url.includes("/findings")) {
      return json(200, {
        snapshot_id: REF,
        findings: [{ id: "f1", file: "src/other/x.py" }],
      });
    }
    if (url.endsWith("/ask")) {
      const next = asks[n++]!;
      return "status" in next && typeof next.status === "number" && "body" in next
        ? json(next.status, next.body)
        : json(200, next);
    }
    return json(200, { meta: { licence: "MIT" }, analyzers: [] });
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Interview screen", () => {
  it("renders every claim kind through the shell, expands ancestors, shows the licence, and passes axe", async () => {
    mockApi([answered, declined]);
    const user = userEvent.setup();
    const { container } = render(<App snapshotRef={REF} />);
    await waitFor(() => expect(screen.getByText("src")).toBeTruthy());

    const input = screen.getByLabelText("Ask the spirit");
    await user.type(input, "Why do you break?{Enter}");

    const banished = await screen.findByTestId("banishment");
    expect(banished.querySelector("del")?.textContent).toBe("It was written by a fool.");
    expect(screen.getByText("BANISHED")).toBeTruthy();
    expect(screen.getByText(/leap year/).closest("p")?.getAttribute("data-kind")).toBe("guess");
    expect(screen.getByText(/not moved/).closest("p")?.getAttribute("data-kind")).toBe("fact");

    // The cited file's ancestors are expanded and the file is visible and marked.
    const tree = screen.getByRole("tree");
    for (const dir of ["src", "src/pkg"]) {
      const item = tree.querySelector(`[data-path="${dir}"]`);
      expect(item?.getAttribute("aria-expanded")).toBe("true");
    }
    expect(tree.querySelector('[data-path="src/pkg/mod.py"]')?.getAttribute("data-cited")).toBe("true");

    // The licence comes from the snapshot.
    expect(screen.getByText(/Licence: MIT/)).toBeTruthy();

    await user.type(screen.getByLabelText("Ask the spirit"), "Who knows?{Enter}");
    const decline = await screen.findByTestId("decline-line");
    expect(decline.textContent).toBe("The spirits are silent on that.");

    expect((await axe(container)).violations).toEqual([]);
  });

  it("submits on Enter exactly once and posts to the ask route", async () => {
    const fn = mockApi([answered]);
    const user = userEvent.setup();
    render(<App snapshotRef={REF} />);
    await user.type(screen.getByLabelText("Ask the spirit"), "Hello?{Enter}");
    await screen.findByTestId("banishment");
    const posts = fn.mock.calls.filter(([url]) => url.endsWith("/ask"));
    expect(posts).toHaveLength(1);
    expect(JSON.parse(String(posts[0]![1]?.body))).toEqual({ persona: "ghost", question: "Hello?" });
  });

  it("shows a structured API error code in the error region", async () => {
    mockApi([{ status: 404, body: { error: { code: "snapshot_not_found", message: "no such snapshot" } } }]);
    const user = userEvent.setup();
    render(<App snapshotRef={REF} />);
    await user.type(screen.getByLabelText("Ask the spirit"), "Anyone?{Enter}");
    await waitFor(() => {
      const region = screen.getByTestId("error-region");
      expect(within(region).getByText(/snapshot_not_found/)).toBeTruthy();
      expect(region.getAttribute("aria-live")).toBe("assertive");
    });
  });
});
