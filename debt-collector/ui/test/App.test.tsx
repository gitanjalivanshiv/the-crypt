import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { App } from "../src/App";
import type { AnswerResult, Ledger } from "../src/api";

// Validates: Requirements 6.4 to 6.10
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

const LEDGER: Ledger = {
  snapshot_id: "snap-1",
  lines: [
    {
      rank: 1,
      finding_id: "f-aaa",
      analyzer: "churn",
      file: "src/big.py",
      line_start: 10,
      line_end: 59,
      severity: 0.8,
      principal: 50,
      interest: 32,
      boss: true,
      metrics: { commit_count: 120 },
    },
    {
      rank: 2,
      finding_id: "f-bbb",
      analyzer: "staleness",
      file: "src/old.py",
      line_start: 1,
      line_end: 10,
      severity: 0.5,
      principal: 10,
      interest: 2.5,
      boss: false,
      metrics: { days_since_modified: 847 },
    },
  ],
  totals: { principal: 60, interest: 34.5, severity: 1.3 },
  escalation: "reminder",
  coverage: [{ analyzer: "churn", returned: 1, matching: 1 }],
  truncated: false,
};

const NOTICE: AnswerResult = {
  snapshot_id: "snap-1",
  status: "answered",
  claims: [
    {
      kind: "fact",
      text: "Verified debt claim",
      citations: [{ file: "src/big.py", line_start: 10, line_end: 12 }],
      figures: [],
    },
    { kind: "guess", text: "Guessed debt claim", citations: [], figures: [] },
  ],
  banishments: [
    {
      claim_text: "Invented interest claim",
      reason: "unbacked_number",
      message: "number not in the ledger",
      attempt: 1,
      snapshot_id: "snap-1",
    },
  ],
  decline_line: "The accounts are closed.",
  attempts: [],
};

interface Routes {
  ledger?: () => Response;
  notice?: () => Response;
}
function stub(routes: Routes = {}) {
  const f = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/ledger")) return (routes.ledger ?? (() => json(LEDGER)))();
    if (url.endsWith("/notice")) {
      expect(init?.method).toBe("POST");
      return (routes.notice ?? (() => json(NOTICE)))();
    }
    return json({ meta: { snapshot_id: "snap-1", licence: "MIT" } });
  });
  vi.stubGlobal("fetch", f);
  return f;
}
const noticeCalls = (f: ReturnType<typeof stub>) => f.mock.calls.filter(([u]) => String(u).endsWith("/notice"));
const meter = () => screen.getByRole("meter", { name: "Outstanding interest" });

describe("App", () => {
  it("renders every ledger line with its numbers and units", async () => {
    stub();
    render(<App snapshotRef="snap-1" />);
    await screen.findByRole("list", { name: "Ledger" });
    const rows = screen.getAllByRole("listitem").filter((li) => li.hasAttribute("data-boss") || li.querySelector("code"));
    expect(rows).toHaveLength(2);
    const first = rows[0]!;
    expect(first).toHaveAttribute("data-boss", "true");
    expect(rows[1]).not.toHaveAttribute("data-boss");
    for (const text of ["#1", "src/big.py:10-59", "f-aaa", "Severity 0.8", "Principal 50 lines", "Interest 32 lines per year", "commit_count: 120 commits"]) {
      expect(first).toHaveTextContent(text);
    }
    expect(rows[1]).toHaveTextContent("days_since_modified: 847 days");
    expect(rows[1]).toHaveTextContent("Interest 2.5 lines per year");
    expect(screen.getByTestId("escalation")).toHaveTextContent("reminder");
    expect(screen.queryByTestId("coverage-note")).toBeNull();
  });

  it("settling lowers the meter and sends no request", async () => {
    const f = stub();
    render(<App snapshotRef="snap-1" />);
    await screen.findByRole("list", { name: "Ledger" });
    const calls = f.mock.calls.length;
    expect(Number(meter().getAttribute("aria-valuenow"))).toBe(1);
    await userEvent.click(screen.getByRole("button", { name: "Mark settled: src/big.py:10-59" }));
    const now = Number(meter().getAttribute("aria-valuenow"));
    expect(now).toBeLessThan(1);
    expect(now).toBeCloseTo(2.5 / 34.5, 6);
    expect(f.mock.calls.length).toBe(calls);
  });

  it("renders the notice through ChatPanel with the banishment struck", async () => {
    stub();
    render(<App snapshotRef="snap-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Serve notice" }));
    const log = await screen.findByRole("log");
    expect(within(log).getByText(/Verified debt claim/)).toBeInTheDocument();
    expect(within(log).getByText(/Guessed debt claim/)).toBeInTheDocument();
    const ban = within(log).getByTestId("banishment");
    expect(ban.querySelector("del")).toHaveTextContent("Invented interest claim");
    expect(ban).toHaveTextContent("number not in the ledger");
    expect(within(log).queryByTestId("decline-line")).toBeNull();
    expect(log).toHaveTextContent("Licence: MIT");
    expect(log).toHaveTextContent("Snapshot ID: snap-1");
  });

  it("renders a declined notice's decline line through ChatPanel", async () => {
    const declined: AnswerResult = { ...NOTICE, status: "declined", claims: [], banishments: [] };
    stub({ notice: () => json(declined) });
    render(<App snapshotRef="snap-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Serve notice" }));
    expect(await screen.findByTestId("decline-line")).toHaveTextContent("The accounts are closed.");
    expect(screen.getByRole("list", { name: "Ledger" })).toBeInTheDocument();
  });

  it("shows a failed notice's error code and keeps the ledger", async () => {
    stub({ notice: () => json({ error: { code: "snapshot_not_found", message: "no such snapshot" } }, 404) });
    render(<App snapshotRef="snap-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Serve notice" }));
    await waitFor(() => expect(screen.getByTestId("error-region")).toHaveTextContent("snapshot_not_found"));
    expect(screen.getByRole("list", { name: "Ledger" })).toBeInTheDocument();
    expect(meter()).toBeInTheDocument();
    expect(screen.queryByRole("log")).toBeNull();
  });

  it("keeps the ledger and meter when the notice route rejects", async () => {
    const f = stub();
    f.mockImplementation(async (url: string) => {
      if (url.endsWith("/notice")) throw new TypeError("model down");
      if (url.endsWith("/ledger")) return json(LEDGER);
      return json({ meta: { snapshot_id: "snap-1", licence: "MIT" } });
    });
    render(<App snapshotRef="snap-1" />);
    await userEvent.click(await screen.findByRole("button", { name: "Serve notice" }));
    await waitFor(() => expect(screen.getByTestId("error-region")).toHaveTextContent("network_error"));
    expect(screen.getByRole("list", { name: "Ledger" })).toBeInTheDocument();
    expect(meter()).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Serve notice" })).toBeEnabled();
  });

  it("ignores a second submit while a notice is pending", async () => {
    let release: (r: Response) => void = () => undefined;
    const f = stub({ notice: () => new Response() });
    f.mockImplementation(async (url: string) => {
      if (url.endsWith("/notice")) return new Promise<Response>((r) => (release = r));
      if (url.endsWith("/ledger")) return json(LEDGER);
      return json({ meta: { snapshot_id: "snap-1", licence: "MIT" } });
    });
    render(<App snapshotRef="snap-1" />);
    const btn = await screen.findByRole("button", { name: "Serve notice" });
    await userEvent.click(btn);
    expect(btn).toBeDisabled();
    await userEvent.click(btn);
    expect(noticeCalls(f)).toHaveLength(1);
    release(json(NOTICE));
    await screen.findByRole("log");
  });

  it("shows the coverage note when the ledger is truncated", async () => {
    stub({ ledger: () => json({ ...LEDGER, truncated: true, coverage: [{ analyzer: "churn", returned: 100, matching: 250 }] }) });
    render(<App snapshotRef="snap-1" />);
    const note = await screen.findByTestId("coverage-note");
    expect(note).toHaveTextContent("churn: 100 of 250");
  });

  it("has no axe violations", async () => {
    stub();
    const { container } = render(<App snapshotRef="snap-1" />);
    await screen.findByRole("list", { name: "Ledger" });
    await userEvent.click(screen.getByRole("button", { name: "Serve notice" }));
    await screen.findByRole("log");
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
