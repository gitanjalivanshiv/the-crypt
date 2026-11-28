import { afterEach, describe, expect, it, vi } from "vitest";

import { ask, getFindings, getPlan, getSnapshot } from "../src/api";
import { ApiError } from "../src/types";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn(
    async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(body), { status }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("GETs the snapshot", async () => {
    const fn = mockFetch(200, { meta: {}, analyzers: [] });
    await getSnapshot("abc");
    expect(fn).toHaveBeenCalledWith("/snapshots/abc", undefined);
  });

  it("GETs findings with only the query params given", async () => {
    const fn = mockFetch(200, { findings: [] });
    await getFindings("abc", { analyzer: "churn", limit: 5 });
    expect(fn.mock.calls[0]?.[0]).toBe("/snapshots/abc/findings?analyzer=churn&limit=5");
  });

  it("POSTs ask with persona ghost and the question", async () => {
    const fn = mockFetch(200, { status: "answered", claims: [] });
    await ask("abc", "why do you break on the 31st?");
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/snapshots/abc/ask");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      persona: "ghost",
      question: "why do you break on the 31st?",
    });
  });

  it("POSTs the plan route under /medium", async () => {
    const fn = mockFetch(200, { snapshot_id: "abc", sections: [] });
    const plan = await getPlan("abc");
    const [url, init] = fn.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/medium/snapshots/abc/plan");
    expect(init.method).toBe("POST");
    expect(plan.snapshot_id).toBe("abc");
  });

  it("surfaces a structured error as ApiError with code and message", async () => {
    mockFetch(404, { error: { code: "snapshot_not_found", message: "no such snapshot" } });
    const err = await ask("nope", "hi").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({
      code: "snapshot_not_found",
      message: "no such snapshot",
      status: 404,
    });
  });

  it("gives an unstructured failure the code 'unknown'", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("boom", { status: 502 })));
    const err = await getSnapshot("abc").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect((err as ApiError).code).toBe("unknown");
  });

  it("maps a network failure to ApiError 'network'", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("down"))));
    const err = await getSnapshot("abc").catch((e: unknown) => e);
    expect((err as ApiError).code).toBe("network");
  });
});
