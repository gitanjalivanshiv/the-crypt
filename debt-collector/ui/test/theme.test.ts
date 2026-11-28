import { describe, expect, it } from "vitest";
import { MIN_CONTRAST_RATIO, REQUIRED_PAIRS, contrastRatio } from "@kiroween/ui-shell";
import { ledger } from "../src/theme/ledger";

describe("ledger theme", () => {
  it("has id ledger", () => {
    expect(ledger.id).toBe("ledger");
  });

  it.each(REQUIRED_PAIRS.map((p) => [p[0], p[1]] as const))(
    "%s on %s meets the minimum contrast ratio",
    (fg, bg) => {
      expect(contrastRatio(ledger.colours[fg], ledger.colours[bg])).toBeGreaterThanOrEqual(
        MIN_CONTRAST_RATIO,
      );
    },
  );

  it("keeps every effect within 0..1, with flicker off and a visible bezel", () => {
    for (const v of Object.values(ledger.effects)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
    expect(ledger.effects.flicker).toBe(0);
    expect(ledger.effects.glow).toBeGreaterThan(0);
    expect(ledger.effects.scanlines).toBeGreaterThan(0);
  });

  it("declares no sounds yet", () => {
    expect(ledger.sounds).toEqual({});
  });
});
