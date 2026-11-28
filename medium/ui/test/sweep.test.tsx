import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SWEEP_INTERVAL_MS, useSweep } from "../src/useSweep";

const FILES = ["a.py", "b.py", "c.py"];

function stubMotion(reduce: boolean) {
  vi.stubGlobal(
    "matchMedia",
    (query: string) =>
      ({
        matches: reduce && query.includes("reduce"),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  );
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

describe("useSweep", () => {
  it("steps through cited files in order and stops on the last", () => {
    const { result } = renderHook(() => useSweep(FILES));
    expect(result.current).toBe("a.py");
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS));
    expect(result.current).toBe("b.py");
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS));
    expect(result.current).toBe("c.py");
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS * 3));
    expect(result.current).toBe("c.py");
  });

  it("returns the first cited file and starts no timer under reduced motion", () => {
    stubMotion(true);
    const spy = vi.spyOn(globalThis, "setInterval");
    const { result } = renderHook(() => useSweep(FILES));
    expect(result.current).toBe("a.py");
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS * 5));
    expect(result.current).toBe("a.py");
    expect(spy).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("holds position while paused by a user selection", () => {
    const { result, rerender } = renderHook(({ paused }) => useSweep(FILES, paused), {
      initialProps: { paused: false },
    });
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS));
    expect(result.current).toBe("b.py");
    rerender({ paused: true });
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS * 3));
    expect(result.current).toBe("b.py");
  });

  it("restarts from the first file when the cited set changes, and is null when empty", () => {
    const { result, rerender } = renderHook(({ files }) => useSweep(files), {
      initialProps: { files: FILES },
    });
    act(() => void vi.advanceTimersByTime(SWEEP_INTERVAL_MS));
    rerender({ files: ["x.py", "y.py"] });
    expect(result.current).toBe("x.py");
    rerender({ files: [] });
    expect(result.current).toBeNull();
  });
});
