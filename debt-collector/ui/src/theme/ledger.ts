import type { Theme } from "@kiroween/ui-shell";

/**
 * The Debt Collector's theme: ink on paper, with a visible bezel and faint
 * scanlines so the ledger still reads as a screen. Data only, no component.
 * Palette is the shell's reference ledger palette (contrast-checked in
 * test/theme.test.ts). `sounds` is empty until the cuttable sound task.
 */
export const ledger: Theme = {
  id: "ledger",
  colours: {
    bg: "#f6f1e4",
    panel: "#ebe3d0",
    text: "#1f1b14",
    textMuted: "#4f473a",
    accent: "#7a3b00",
    cite: "#0b4f8a",
    danger: "#a11a1a",
  },
  font: {
    family: 'Georgia, "Times New Roman", serif',
    sizeBase: "17px",
  },
  // glow drives the visible bezel; flicker stays 0 so figures hold still.
  effects: { glow: 0.4, scanlines: 0.15, flicker: 0 },
  sounds: {},
};
