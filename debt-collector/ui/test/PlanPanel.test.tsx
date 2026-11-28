import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { PlanPanel } from "../src/PlanPanel";
import type { PlanResult } from "../src/api";

// Validates: Requirements 5.2, 5.3, 6.8
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

// Deliberately not sorted by rank or ratio: the panel must keep this order.
const PLAN: PlanResult = {
  snapshot_id: "snap-1",
  entries: [
    {
      rank: 2,
      finding_id: "f-bbb",
      source: { file: "src/old.py", line_start: 1, line_end: 10 },
      effort: 10,
      interest: 2.5,
      interest_per_effort: 0.25,
      boss: false,
    },
    {
      rank: 1,
      finding_id: "f-aaa",
      source: { file: "src/big.py", line_start: 10, line_end: 59 },
      effort: 50,
      interest: 32.123457,
      interest_per_effort: 0.642469,
      boss: true,
    },
  ],
};

const button = () => screen.getByRole("button", { name: /repayment plan/i });

describe("PlanPanel", () => {
  it("renders entries in the order received with every figure as returned", async () => {
    const f = vi.fn(async (_url: string) => json(PLAN));
    vi.stubGlobal("fetch", f);
    const { container } = render(<PlanPanel snapshotRef="snap-1" />);
    expect(screen.queryByRole("list")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Show repayment plan" }));
    const items = await screen.findAllByTestId("plan-entry");
    expect(String(f.mock.calls[0]![0])).toBe("/collector/snapshots/snap-1/plan");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("#2");
    expect(items[0]).toHaveTextContent("src/old.py:1-10");
    expect(items[0]).toHaveTextContent("f-bbb");
    expect(items[0]).toHaveTextContent("Effort 10");
    expect(items[0]).toHaveTextContent("Interest 2.5.");
    expect(items[0]).toHaveTextContent("Interest per effort 0.25");
    expect(items[1]).toHaveTextContent("#1");
    expect(items[1]).toHaveTextContent("src/big.py:10-59");
    expect(items[1]).toHaveTextContent("Interest 32.123457.");
    expect(items[1]).toHaveTextContent("Interest per effort 0.642469");
    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("shows the structured error and no partial plan", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ error: { code: "snapshot_not_found", message: "no such snapshot" } }, 404)),
    );
    render(<PlanPanel snapshotRef="nope" />);
    await userEvent.click(button());
    await waitFor(() =>
      expect(screen.getByTestId("plan-error")).toHaveTextContent("snapshot_not_found: no such snapshot"),
    );
    expect(screen.getByTestId("plan-error")).toHaveAttribute("aria-live", "assertive");
    expect(screen.queryByTestId("plan-entry")).toBeNull();
    expect(button()).toBeEnabled();
  });

  it("is pending while loading and ignores a second submit", async () => {
    let release: (r: Response) => void = () => undefined;
    const f = vi.fn(() => new Promise<Response>((resolve) => (release = resolve)));
    vi.stubGlobal("fetch", f);
    render(<PlanPanel snapshotRef="snap-1" />);
    const user = userEvent.setup();
    await user.click(button());
    expect(button()).toBeDisabled();
    expect(button()).toHaveAttribute("aria-busy", "true");
    await user.click(button());
    await user.keyboard("{Enter}");
    expect(f).toHaveBeenCalledTimes(1);
    release(json(PLAN));
    await screen.findAllByTestId("plan-entry");
    expect(button()).toBeEnabled();
  });
});
