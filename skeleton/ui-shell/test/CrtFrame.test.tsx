import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { axe } from "vitest-axe";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CrtFrame } from "../src/components/CrtFrame";
import { ThemeProvider } from "../src/theme/ThemeProvider";
import { phosphor } from "../src/theme/themes/phosphor";


function mockReducedMotion(matches: boolean) {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockImplementation(() => ({
      matches,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderFrame() {
  return render(
    <ThemeProvider theme={phosphor}>
      <CrtFrame>
        <p>inside</p>
      </CrtFrame>
    </ThemeProvider>,
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("CrtFrame", () => {
  it("renders its children", () => {
    mockReducedMotion(false);
    renderFrame();
    expect(screen.getByText("inside")).toBeTruthy();
  });

  it("keeps the overlay out of the DOM and the a11y tree", () => {
    mockReducedMotion(false);
    const { container } = renderFrame();
    const frame = container.querySelector("[data-crt-frame]") as HTMLElement;
    // The overlay is a ::after pseudo-element, so the frame has only its children.
    expect(Array.from(frame.children).map((c) => c.tagName)).toEqual(["P"]);
    const css = readFileSync(resolve(import.meta.dirname, "../src/components/CrtFrame.module.css"), "utf8");
    const after = css.match(/\.frame::after\s*\{[^}]*\}/)?.[0] ?? "";
    expect(after).toContain("pointer-events: none");
    expect(after).toContain('content: ""');
  });

  it("adds animation classes when motion is allowed", () => {
    mockReducedMotion(false);
    const { container } = renderFrame();
    const frame = container.querySelector("[data-crt-frame]") as HTMLElement;
    expect(frame.className).toMatch(/flicker/);
    expect(frame.className).toMatch(/scanlinesMoving/);
  });

  it("removes animation classes under reduced motion", () => {
    mockReducedMotion(true);
    const { container } = renderFrame();
    const frame = container.querySelector("[data-crt-frame]") as HTMLElement;
    expect(frame.className).not.toMatch(/flicker/);
    expect(frame.className).not.toMatch(/scanlinesMoving/);
  });

  it("has no accessibility violations", async () => {
    mockReducedMotion(false);
    const { container } = renderFrame();
    expect((await axe(container)).violations).toEqual([]);
  });
});
