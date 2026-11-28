import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import type { AnswerResult, Ledger } from "../src/api";
import { SOUND_EVENTS, ledger as ledgerTheme } from "../src/theme/ledger";

// Validates: Requirements 6.2, 6.9
const spy = vi.hoisted(() => ({ play: null as null | ((name: string) => void) }));

vi.mock("@kiroween/ui-shell", async (orig) => {
  const actual = await orig<typeof import("@kiroween/ui-shell")>();
  return {
    ...actual,
    useSound: () => {
      const real = actual.useSound();
      return spy.play ? { ...real, play: spy.play } : real;
    },
  };
});

afterEach(() => {
  cleanup();
  spy.play = null;
  vi.unstubAllGlobals();
});

const json = (body: unknown): Response =>
  new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });

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
  ],
  totals: { principal: 50, interest: 32, severity: 0.8 },
  escalation: "reminder",
  coverage: [{ analyzer: "churn", returned: 1, matching: 1 }],
  truncated: false,
};

const banishment = (n: number) => ({
  claim_text: `Invented claim ${n}`,
  reason: "unbacked_number" as const,
  message: "number not in the ledger",
  attempt: 1,
  snapshot_id: "snap-1",
});

const NOTICE: AnswerResult = {
  snapshot_id: "snap-1",
  status: "answered",
  claims: [],
  banishments: [banishment(1), banishment(2)],
  decline_line: null,
  attempts: [],
};

function stubFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.endsWith("/ledger")) return json(LEDGER);
      if (url.endsWith("/notice")) return json(NOTICE);
      return json({ meta: { snapshot_id: "snap-1", licence: "MIT" } });
    }),
  );
}

async function playAll(): Promise<string[]> {
  const played: string[] = [];
  spy.play = (name) => void played.push(name);
  stubFetch();
  const user = userEvent.setup();
  render(<App snapshotRef="snap-1" />);
  await user.click(await screen.findByRole("button", { name: /Mark settled/ }));
  await user.click(screen.getByRole("button", { name: "Serve notice" }));
  await waitFor(() => expect(played).toContain("notice"));
  return played;
}

describe("sound cues", () => {
  it("plays settle, notice, and one banish per banishment", async () => {
    const played = await playAll();
    expect(played).toEqual(["settle", "notice", "banish", "banish"]);
  });

  it("every event App plays has a spec in the theme", async () => {
    const played = await playAll();
    for (const name of new Set([...played, ...SOUND_EVENTS])) {
      expect(ledgerTheme.sounds[name], name).toBeDefined();
    }
  });

  it("a muted provider plays nothing", async () => {
    const oscillators = vi.fn();
    const ctx = {
      createOscillator: oscillators,
      createGain: vi.fn(),
      resume: vi.fn(),
      currentTime: 0,
      destination: {},
    };
    vi.stubGlobal("AudioContext", vi.fn(() => ctx));
    const audio = vi.fn();
    vi.stubGlobal("Audio", audio);
    stubFetch();
    const user = userEvent.setup();
    render(<App snapshotRef="snap-1" />);
    await user.click(await screen.findByRole("button", { name: /Mark settled/ }));
    await user.click(screen.getByRole("button", { name: "Serve notice" }));
    await screen.findAllByTestId("banishment");
    expect(oscillators).not.toHaveBeenCalled();
    expect(audio).not.toHaveBeenCalled();
  });
});
