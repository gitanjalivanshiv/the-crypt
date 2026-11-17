import type { Theme } from "../../src/theme/types";

/** Third theme, defined only as data. Used to prove themes need no component edits. */
export const themeC: Theme = {
  id: "amber-terminal",
  colours: {
    bg: "#1a1200",
    panel: "#2a1e00",
    text: "#ffcf5c",
    textMuted: "#d9a93a",
    accent: "#ffb000",
    cite: "#7fd4ff",
    danger: "#ff8a80",
  },
  font: { family: '"Courier New", monospace', sizeBase: "16px" },
  effects: { glow: 0.4, scanlines: 0.2, flicker: 0.1 },
  sounds: {
    send: { kind: "tone", freq: 660, ms: 40, wave: "square" },
    receive: { kind: "tone", freq: 330, ms: 60, wave: "square" },
    banish: { kind: "tone", freq: 110, ms: 200, wave: "sawtooth" },
  },
};
