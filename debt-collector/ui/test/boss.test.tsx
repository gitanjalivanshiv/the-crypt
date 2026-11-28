import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { App } from "../src/App";
import type { Ledger } from "../src/api";

// Validates: Requirements 1.8, 6.3, 6.9
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const line = (rank: number, boss: boolean) => ({
  rank,
  finding_id: `f-${rank}`,
  analyzer: "churn",
  file: `src/f${rank}.py`,
  line_start: 1,
  line_end: 10,
  severity: 0.5,
  principal: 10,
  interest: 5,
  boss,
  metrics: { commit_count: 3 },
});

const LEDGER: Ledger = {
  snapshot_id: "snap-1",
  lines: [line(1, true), line(2, true), line(3, false)],
  totals: { principal: 30, interest: 15, severity: 1.5 },
  escalation: "reminder",
  coverage: [{ analyzer: "churn", returned: 3, matching: 3 }],
  truncated: false,
};

function stub() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      new Response(JSON.stringify(String(url).endsWith("/ledger") ? LEDGER : { meta: { snapshot_id: "snap-1", licence: "MIT" } }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    ),
  );
}

const rows = () => screen.getAllByRole("listitem").filter((li) => li.querySelector("code"));

describe("boss rows", () => {
  it("only boss rows carry the label, which is in the accessibility tree", async () => {
    stub();
    render(<App snapshotRef="snap-1" />);
    await screen.findByRole("list", { name: "Ledger" });
    const [a, b, c] = rows();
    for (const r of [a!, b!]) {
      expect(r).toHaveAttribute("data-boss", "true");
      expect(r).toHaveTextContent("Largest debt");
    }
    expect(c).not.toHaveAttribute("data-boss");
    expect(c).not.toHaveTextContent("Largest debt");
    // Real text (not CSS content), so role queries and screen readers see it.
    expect(screen.getAllByText("Largest debt")).toHaveLength(2);
    expect(screen.getAllByText("Largest debt")[0]).toBeVisible();
    expect(screen.getAllByText("Largest debt")[0]).not.toHaveAttribute("aria-hidden");
  });

  it("still renders the rows with every stylesheet removed", async () => {
    stub();
    document.querySelectorAll("style, link[rel=stylesheet]").forEach((n) => n.remove());
    render(<App snapshotRef="snap-1" />);
    await screen.findByRole("list", { name: "Ledger" });
    expect(rows()).toHaveLength(3);
    expect(document.querySelectorAll('li[data-boss="true"]')).toHaveLength(2);
  });

  it("styles by data-boss, uses theme variables and disables the pulse under reduced motion", () => {
    const css = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "..", "src", "boss.css"), "utf8");
    expect(css).toContain('[data-boss="true"]');
    expect(css).toContain("var(--crypt-colour-danger)");
    expect(css).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\)[\s\S]*animation: none/);
  });

  it("has no axe violations", async () => {
    stub();
    const { container } = render(<App snapshotRef="snap-1" />);
    await screen.findByRole("list", { name: "Ledger" });
    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
