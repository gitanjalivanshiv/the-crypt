import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Meter } from "../src/components/Meter";

function mockReducedMotion(matches: boolean): void {
  vi.stubGlobal(
    "matchMedia",
    (query: string): MediaQueryList =>
      ({
        matches,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        addListener: () => {},
        removeListener: () => {},
        dispatchEvent: () => false,
      }) as MediaQueryList,
  );
}

function fill(): Element {
  return screen.getByRole("meter").firstElementChild as Element;
}

// Validates: Requirements 6.7, 6.13
describe("Meter motion", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("has the transition class normally", () => {
    mockReducedMotion(false);
    render(<Meter value={0.5} label="Level" />);
    expect(fill().className).toMatch(/animated/);
  });

  it("drops the transition class under prefers-reduced-motion", () => {
    mockReducedMotion(true);
    render(<Meter value={0.5} label="Level" />);
    expect(fill().className).not.toMatch(/animated/);
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("0.5");
  });
});
