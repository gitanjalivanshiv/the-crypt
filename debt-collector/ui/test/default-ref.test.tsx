/**
 * The bare URL must serve a real ledger. Before the default ref existed the collector
 * requested an empty ref and the judge saw a load error. See docs/DEPLOY-PLAN.md.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "../src/App";

// vitest runs with cwd at the package root; `import.meta.url` is not a file URL here.
const patient = JSON.parse(
  readFileSync(resolve(process.cwd(), "../../demo/patient.json"), "utf8"),
) as { primary: { commit: string } };

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("default snapshot ref", () => {
  it("is the pinned patient commit, not a copy that can drift", () => {
    expect(__DEFAULT_REF__).toBe(patient.primary.commit);
  });

  it("asks for the pinned snapshot when the URL carries none", async () => {
    const seen: string[] = [];
    vi.stubGlobal("fetch", (input: RequestInfo | URL) => {
      seen.push(String(input));
      return Promise.resolve(
        new Response("{}", { status: 500, headers: { "content-type": "application/json" } }),
      );
    });

    render(<App />);

    await waitFor(() => expect(seen.length).toBeGreaterThan(0));
    expect(seen.some((u) => u.includes(`/collector/snapshots/${__DEFAULT_REF__}/ledger`))).toBe(
      true,
    );
    expect(seen.every((u) => !u.includes("/snapshots//"))).toBe(true);
  });
});
