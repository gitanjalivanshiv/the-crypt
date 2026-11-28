import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, getLedger, getPlan, getSnapshot, postNotice } from "../src/api";
import type { AnswerResult, Ledger, LedgerLine } from "../src/api";
import {
  formatNumber,
  initialState,
  meterValue,
  outstanding,
  reducer,
  settle,
  submitNotice,
} from "../src/state";
import type { CollectorAction, CollectorState } from "../src/state";

afterEach(() => vi.unstubAllGlobals());

const json = (body: unknown, status = 200): Response =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

function stubFetch(res: () => Response) {
  const f = vi.fn(async () => res());
  vi.stubGlobal("fetch", f);
  return f;
}

function line(i: number, interest: number): LedgerLine {
  return {
    rank: i + 1,
    finding_id: `f${i}`,
    analyzer: "churn",
    file: "a.py",
    line_start: 1,
    line_end: 2,
    severity: 0.5,
    principal: 2,
    interest,
    boss: false,
    metrics: {},
  };
}

function ledgerOf(interests: number[]): Ledger {
  const total = Number(interests.reduce((a, b) => a + b, 0).toFixed(6));
  return {
    snapshot_id: "s",
    lines: interests.map((v, i) => line(i, v)),
    totals: { principal: 0, interest: total, severity: 0 },
    escalation: "courtesy",
    coverage: [],
    truncated: false,
  };
}

const answer: AnswerResult = {
  snapshot_id: "s",
  status: "declined",
  claims: [],
  banishments: [],
  decline_line: "The spirits are silent on that",
  attempts: [],
};

describe("api wrappers", () => {
  it("calls the four routes with the right method and no body", async () => {
    const f = stubFetch(() => json({}));
    await getSnapshot("a/b");
    await getLedger("abc");
    await getPlan("abc");
    await postNotice("abc");
    const calls = f.mock.calls as unknown as [string, RequestInit | undefined][];
    expect(calls.map((c) => c[0])).toEqual([
      "/snapshots/a%2Fb",
      "/collector/snapshots/abc/ledger",
      "/collector/snapshots/abc/plan",
      "/collector/snapshots/abc/notice",
    ]);
    const inits = calls.map((c) => c[1]);
    expect(inits[0]).toBeUndefined();
    expect(inits[3]).toEqual({ method: "POST" });
    expect(inits[3]?.body).toBeUndefined();
  });

  it("returns the parsed ledger", async () => {
    const l = ledgerOf([1, 2]);
    stubFetch(() => json(l));
    expect(await getLedger("abc")).toEqual(l);
  });

  it("turns a structured error into an ApiError with code and message", async () => {
    stubFetch(() => json({ error: { code: "snapshot_not_found", message: "no such snapshot" } }, 404));
    const err = await getLedger("x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ code: "snapshot_not_found", message: "no such snapshot", status: 404 });
  });

  it("gives an ApiError for an unstructured failure and for a network error", async () => {
    stubFetch(() => new Response("boom", { status: 500 }));
    await expect(getPlan("x")).rejects.toMatchObject({ code: "http_error", status: 500 });
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    await expect(getPlan("x")).rejects.toMatchObject({ code: "network_error", message: "down" });
  });
});

// Seeded generator: the same cases on every run.
function prng(seed: number): () => number {
  let s = seed >>> 0;
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0;
    return s / 2 ** 32;
  };
}

describe("CP13 meter", () => {
  it("stays in [0, 1], falls as debts are settled, and is 0 when the total is 0", () => {
    const rand = prng(13);
    for (let run = 0; run < 300; run++) {
      const n = Math.floor(rand() * 12);
      const interests = Array.from({ length: n }, () =>
        rand() < 0.2 ? 0 : Number((rand() * 100).toFixed(6)),
      );
      const ledger = ledgerOf(interests);
      const order = ledger.lines.map((l) => l.finding_id).sort(() => rand() - 0.5);
      let settled: ReadonlySet<string> = new Set();
      let prev = meterValue(ledger, settled);
      expect(prev).toBeGreaterThanOrEqual(0);
      expect(prev).toBeLessThanOrEqual(1);
      if (ledger.totals.interest === 0) expect(prev).toBe(0);
      else expect(prev).toBe(1);
      for (const id of order) {
        settled = settle(settled, id);
        const v = meterValue(ledger, settled);
        expect(v).toBeGreaterThanOrEqual(0);
        expect(v).toBeLessThanOrEqual(1);
        expect(v).toBeLessThanOrEqual(prev);
        prev = v;
      }
      expect(prev).toBe(0);
    }
  });

  it("outstanding sums unsettled interest and ignores unknown ids", () => {
    const l = ledgerOf([1.5, 2.25, 3]);
    expect(outstanding(l, new Set())).toBe(6.75);
    expect(outstanding(l, new Set(["f1", "nope"]))).toBe(4.5);
    expect(meterValue(l, new Set(["f0", "f1", "f2"]))).toBe(0);
  });

  it("settle does not change its input", () => {
    const a: ReadonlySet<string> = new Set(["f0"]);
    const b = settle(a, "f1");
    expect([...a]).toEqual(["f0"]);
    expect([...b]).toEqual(["f0", "f1"]);
  });
});

describe("formatNumber", () => {
  it("keeps six places, drops trailing zeros, and does not round further", () => {
    expect(formatNumber(1.234567)).toBe("1.234567");
    expect(formatNumber(2)).toBe("2");
    expect(formatNumber(0.5)).toBe("0.5");
    expect(formatNumber(0.000001)).toBe("0.000001");
    expect(formatNumber(-0)).toBe("0");
  });
});

function store(initial: CollectorState = initialState) {
  let state = initial;
  return {
    get: () => state,
    dispatch: (a: CollectorAction) => {
      state = reducer(state, a);
    },
  };
}

describe("reducer and submit", () => {
  it("settling sends no request", () => {
    const f = stubFetch(() => json({}));
    const s = store();
    s.dispatch({ type: "settle", id: "f0" });
    expect(s.get().settled.has("f0")).toBe(true);
    expect(f).not.toHaveBeenCalled();
  });

  it("ignores a second submit while pending", async () => {
    const s = store();
    let release!: (r: AnswerResult) => void;
    const post = vi.fn(() => new Promise<AnswerResult>((res) => (release = res)));
    const first = submitNotice(s.get, s.dispatch, post);
    expect(s.get().pending).toBe(true);
    expect(await submitNotice(s.get, s.dispatch, post)).toBe(false);
    expect(post).toHaveBeenCalledTimes(1);
    release(answer);
    expect(await first).toBe(true);
    expect(s.get().pending).toBe(false);
  });

  it("stores the notice as the same object it received", async () => {
    const s = store();
    await submitNotice(s.get, s.dispatch, async () => answer);
    expect(s.get().notice).toBe(answer);
  });

  it("records a failed notice as code and message, leaving settled alone", async () => {
    const s = store();
    s.dispatch({ type: "settle", id: "f0" });
    await submitNotice(s.get, s.dispatch, async () => {
      throw new ApiError("snapshot_not_found", "gone", 404);
    });
    expect(s.get().error).toEqual({ code: "snapshot_not_found", message: "gone" });
    expect(s.get().pending).toBe(false);
    expect(s.get().settled.has("f0")).toBe(true);
  });
});
