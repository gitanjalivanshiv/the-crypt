import { describe, expect, it } from "vitest";
import { contrastRatio } from "../src/theme/contrast";
import { phosphor } from "../src/theme/themes/phosphor";
import { ledger } from "../src/theme/themes/ledger";
import { MIN_CONTRAST_RATIO, REQUIRED_PAIRS, type Theme } from "../src/theme/types";

// No runtime registry exists yet (ThemeProvider is a later task), so the
// registered themes are the reference themes listed here. Add new themes here.
const THEMES: readonly Theme[] = [phosphor, ledger];

const PERSONA_WORDS = /medium|debt[- ]?collector/i;

describe.each(THEMES.map((t) => [t.id, t] as const))("theme %s", (_id, theme) => {
  it.each(REQUIRED_PAIRS.map(([fg, bg]) => [fg, bg] as const))(
    "%s on %s has contrast >= 4.5",
    (fg, bg) => {
      const ratio = contrastRatio(theme.colours[fg], theme.colours[bg]);
      expect(ratio).toBeGreaterThanOrEqual(MIN_CONTRAST_RATIO);
    },
  );

  it("keeps effect values within 0..1", () => {
    for (const v of Object.values(theme.effects)) {
      expect(Number.isFinite(v)).toBe(true);
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("contains no persona names", () => {
    expect(JSON.stringify(theme)).not.toMatch(PERSONA_WORDS);
  });
});

describe("theme registry", () => {
  it("has unique ids", () => {
    expect(new Set(THEMES.map((t) => t.id)).size).toBe(THEMES.length);
  });

  it("rejects a low-contrast theme", () => {
    const bad = contrastRatio("#777777", "#808080");
    expect(bad).toBeLessThan(MIN_CONTRAST_RATIO);
  });
});
