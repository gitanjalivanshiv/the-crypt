import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DRAIN_STEPS, STEP_MS, useDrain } from "../src/useDrain";

// Validates: Requirements 6.6, 6.9
function stubMotion(reduce: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: reduce && q.includes("reduce"),
    media: q,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

beforeEach(() => {
  vi.useFakeTimers();
  stubMotion(false);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("useDrain", () => {
  it("steps down and ends exactly on the target", () => {
    const { result, rerender } = renderHook(({ t }) => useDrain(t), { initialProps: { t: 100 } });
    expect(result.current).toBe(100);
    rerender({ t: 40 });
    act(() => void vi.advanceTimersByTime(STEP_MS));
    const first = result.current;
    expect(first).toBeLessThan(100);
    expect(first).toBeGreaterThan(40);
    act(() => void vi.advanceTimersByTime(STEP_MS * DRAIN_STEPS));
    expect(result.current).toBe(40);
    expect(vi.getTimerCount()).toBe(0);
  });

  it("restarts from the current value when the target changes mid-drain", () => {
    const { result, rerender } = renderHook(({ t }) => useDrain(t), { initialProps: { t: 100 } });
    rerender({ t: 0 });
    act(() => void vi.advanceTimersByTime(STEP_MS * 5));
    const mid = result.current;
    expect(mid).toBeLessThan(100);
    expect(mid).toBeGreaterThan(0);
    rerender({ t: 10 });
    act(() => void vi.advanceTimersByTime(STEP_MS));
    expect(result.current).toBeLessThanOrEqual(mid);
    expect(result.current).toBeGreaterThan(10);
    act(() => void vi.advanceTimersByTime(STEP_MS * DRAIN_STEPS));
    expect(result.current).toBe(10);
  });

  it("returns the target at once with no timer under reduced motion", () => {
    stubMotion(true);
    const { result, rerender } = renderHook(({ t }) => useDrain(t), { initialProps: { t: 100 } });
    rerender({ t: 25 });
    expect(result.current).toBe(25);
    expect(vi.getTimerCount()).toBe(0);
  });
});
