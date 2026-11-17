import { render, screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";
import { Meter } from "../src/components/Meter";

// Validates: Requirements 6.7
describe("Meter", () => {
  it("clamps values above 1 and below 0", () => {
    const { rerender } = render(<Meter value={5} label="Level" />);
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("1");
    rerender(<Meter value={-2} label="Level" />);
    expect(screen.getByRole("meter").getAttribute("aria-valuenow")).toBe("0");
  });

  it("exposes ARIA attributes", () => {
    render(<Meter value={0.4} label="Level" />);
    const m = screen.getByRole("meter");
    expect(m.getAttribute("aria-valuemin")).toBe("0");
    expect(m.getAttribute("aria-valuemax")).toBe("1");
    expect(m.getAttribute("aria-valuenow")).toBe("0.4");
    expect(m.getAttribute("aria-label")).toBe("Level");
  });

  it("has no axe violations", async () => {
    const { container } = render(<Meter value={0.5} label="Level" />);
    expect((await axe(container)).violations).toEqual([]);
  });
});
