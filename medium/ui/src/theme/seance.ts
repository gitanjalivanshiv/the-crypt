import type { Theme } from "@kiroween/ui-shell";

/** The Medium's theme: amber phosphor on near-black, candle-lit. Data only. */
export const seance: Theme = {
  id: "seance",
  colours: {
    bg: "#0d0905",
    panel: "#1a120a",
    text: "#ffb000",
    textMuted: "#c98a2b",
    accent: "#ffd37a",
    cite: "#5fd3c4",
    danger: "#ff6b5a",
  },
  font: {
    family: '"VT323", "IBM Plex Mono", "Courier New", monospace',
    sizeBase: "18px",
  },
  effects: { glow: 0.7, scanlines: 0.35, flicker: 0.15 },
  // Sound cues are added in task 6.8.
  sounds: {},
};
