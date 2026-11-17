import type { Theme } from "../types";

/** Reference theme: green phosphor terminal. Data only. */
export const phosphor: Theme = {
  id: "phosphor",
  colours: {
    bg: "#0a120a",
    panel: "#101c10",
    text: "#7dff9b",
    textMuted: "#6fbf80",
    accent: "#b6ff6e",
    cite: "#6ee7ff",
    danger: "#ff7a7a",
  },
  font: {
    family: '"IBM Plex Mono", "Courier New", monospace',
    sizeBase: "16px",
  },
  effects: { glow: 0.6, scanlines: 0.3, flicker: 0.1 },
  sounds: {
    send: { kind: "tone", freq: 880, ms: 60, wave: "square" },
    receive: { kind: "tone", freq: 660, ms: 80, wave: "square" },
    banish: { kind: "tone", freq: 180, ms: 220, wave: "sawtooth" },
  },
};
