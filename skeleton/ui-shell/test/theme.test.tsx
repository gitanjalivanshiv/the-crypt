import { act, render, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useReducedMotion } from "../src/hooks/useReducedMotion";
import { ThemeProvider } from "../src/theme/ThemeProvider";
import { ledger } from "../src/theme/themes/ledger";
import { phosphor } from "../src/theme/themes/phosphor";

function wrapper(container: HTMLElement): HTMLElement {
  return container.querySelector("[data-crypt-theme-root]") as HTMLElement;
}

describe("ThemeProvider", () => {
  it("writes tokens as --crypt-* properties on the wrapper", () => {
    const { container } = render(<ThemeProvider theme={phosphor}>x</ThemeProvider>);
    const el = wrapper(container);
    expect(el.style.getPropertyValue("--crypt-colour-bg")).toBe(phosphor.colours.bg);
    expect(el.style.getPropertyValue("--crypt-colour-text-muted")).toBe(
      phosphor.colours.textMuted,
    );
    expect(el.style.getPropertyValue("--crypt-font-family")).toBe(phosphor.font.family);
    expect(el.style.getPropertyValue("--crypt-effect-glow")).toBe(
      String(phosphor.effects.glow),
    );
  });

  it("updates tokens when the theme switches", () => {
    const { container, rerender } = render(<ThemeProvider theme={phosphor}>x</ThemeProvider>);
    rerender(<ThemeProvider theme={ledger}>x</ThemeProvider>);
    const el = wrapper(container);
    expect(el.style.getPropertyValue("--crypt-colour-bg")).toBe(ledger.colours.bg);
    expect(el.style.getPropertyValue("--crypt-effect-glow")).toBe("0");
  });
});

describe("useReducedMotion", () => {
  let matches = false;
  let listeners: Array<(e: MediaQueryListEvent) => void> = [];

  beforeEach(() => {
    listeners = [];
    vi.stubGlobal(
      "matchMedia",
      vi.fn((query: string) => ({
        get matches() {
          return matches;
        },
        media: query,
        addEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) =>
          listeners.push(cb),
        removeEventListener: (_: string, cb: (e: MediaQueryListEvent) => void) => {
          listeners = listeners.filter((l) => l !== cb);
        },
      })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    matches = false;
  });

  it("follows the mocked media query", () => {
    matches = false;
    const { result, unmount } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(false);
    expect(window.matchMedia).toHaveBeenCalledWith("(prefers-reduced-motion: reduce)");

    act(() => {
      matches = true;
      listeners.forEach((l) => l({ matches: true } as MediaQueryListEvent));
    });
    expect(result.current).toBe(true);

    unmount();
    expect(listeners).toHaveLength(0);
  });

  it("starts true when the query already matches", () => {
    matches = true;
    const { result } = renderHook(() => useReducedMotion());
    expect(result.current).toBe(true);
  });
});
