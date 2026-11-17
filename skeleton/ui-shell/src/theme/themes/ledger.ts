import type { Theme } from "../types";

/** Reference theme: ink on paper, no effects. Data only. */
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
  effects: { glow: 0, scanlines: 0, flicker: 0 },
  sounds: {
    send: { kind: "tone", freq: 520, ms: 50, wave: "sine" },
    receive: { kind: "tone", freq: 440, ms: 70, wave: "sine" },
    banish: { kind: "tone", freq: 220, ms: 180, wave: "triangle" },
  },
};
