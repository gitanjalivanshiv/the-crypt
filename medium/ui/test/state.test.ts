import { describe, expect, it } from "vitest";
import { active, cited, files, initialState, reducer } from "../src/state";
import type { AnswerResult } from "../src/types";

/** Seeded PRNG (mulberry32) so failures are reproducible. */
function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const cit = (file: string) => ({ file, line_start: 1, line_end: 2, quote: null });
const claim = (kind: "fact" | "guess", ...fs: string[]) => ({
  kind,
  text: "t",
  citations: fs.map(cit),
  figures: [],
});
function result(claims: AnswerResult["claims"], banished: string[] = []): AnswerResult {
  return {
    snapshot_id: "s",
    status: "answered",
    claims,
    banishments: banished.map((f) => ({
      claim_text: "x",
      reason: "file_not_found",
      message: "m",
      target: { type: "citation", index: 0, citation: cit(f) },
      attempt: 1,
      snapshot_id: "s",
    })),
    attempts: [],
  };
}

describe("state derivation", () => {
  it("MP8: banished citations never appear in cited (200 seeded cases)", () => {
    for (let seed = 1; seed <= 200; seed++) {
      const r = rng(seed);
      const n = Math.floor(r() * 6);
      const claims = Array.from({ length: n }, () =>
        claim(
          r() < 0.8 ? "fact" : "guess",
          ...Array.from({ length: Math.floor(r() * 3) }, () => `ok/f${Math.floor(r() * 5)}.py`),
        ),
      );
      const banished = Array.from({ length: Math.floor(r() * 4) }, () => `bad/b${Math.floor(r() * 5)}.py`);
      const out = cited(result(claims, banished));
      for (const b of banished) expect(out).not.toContain(b);
      expect(new Set(out).size).toBe(out.length);
    }
  });

  it("cited keeps first-appearance order, unique, facts only", () => {
    const r = result([claim("fact", "b.py", "a.py"), claim("guess", "g.py"), claim("fact", "b.py", "c.py")]);
    expect(cited(r)).toEqual(["b.py", "a.py", "c.py"]);
  });

  it("files is the sorted union and contains every cited file", () => {
    for (let seed = 1; seed <= 100; seed++) {
      const r = rng(seed);
      let s = reducer(initialState("ref"), {
        type: "loaded",
        licence: "MIT",
        findingFiles: Array.from({ length: Math.floor(r() * 4) }, () => `f${Math.floor(r() * 6)}.py`),
      });
      const results: AnswerResult[] = [];
      for (let i = 0; i < 3; i++) {
        const res = result([claim("fact", `f${Math.floor(r() * 9)}.py`, `d/g${Math.floor(r() * 4)}.py`)]);
        results.push(res);
        s = reducer(s, { type: "answered", question: "q", result: res });
      }
      const out = files(s);
      for (const res of results) for (const f of cited(res)) expect(out).toContain(f);
      expect(out).toEqual([...out].sort());
      expect(new Set(out).size).toBe(out.length);
    }
  });

  it("active is the first cited file, and a selection overrides it without a request", () => {
    const res = result([claim("fact", "x.py", "y.py")]);
    let s = reducer(initialState("ref"), { type: "answered", question: "q", result: res });
    expect(active(s)).toBe("x.py");
    const before = s;
    s = reducer(s, { type: "select", file: "y.py" });
    expect(active(s)).toBe("y.py");
    expect(s.pending).toBe(false);
    expect(s.turns).toBe(before.turns);
  });

  it("active is null with no turns and no selection", () => {
    expect(active(initialState("ref"))).toBeNull();
  });

  it("ignores a second submit while pending", () => {
    const s1 = reducer(initialState("ref"), { type: "submit", question: "a" });
    expect(s1.pending).toBe(true);
    expect(reducer(s1, { type: "submit", question: "b" })).toBe(s1);
  });

  it("failure clears pending and records the error; submit clears it", () => {
    let s = reducer(initialState("ref"), { type: "submit", question: "a" });
    s = reducer(s, { type: "failed", message: "boom" });
    expect(s).toMatchObject({ pending: false, error: "boom" });
    expect(reducer(s, { type: "submit", question: "a" }).error).toBeNull();
  });

  it("stores the AnswerResult by reference", () => {
    const res = result([claim("fact", "a.py")]);
    const s = reducer(initialState("ref"), { type: "answered", question: "q", result: res });
    expect(s.turns[0]?.result).toBe(res);
  });
});
