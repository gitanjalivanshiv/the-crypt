export type SoundSpec =
  | { kind: "tone"; freq: number; ms: number; wave: OscillatorType }
  | { kind: "url"; src: string };

export interface ThemeColours {
  bg: string;
  panel: string;
  text: string;
  textMuted: string;
  accent: string;
  cite: string;
  danger: string;
}

export interface Theme {
  id: string;
  colours: ThemeColours;
  font: { family: string; sizeBase: string };
  /** Each value in the range 0..1. */
  effects: { glow: number; scanlines: number; flicker: number };
  /** Event name -> sound. */
  sounds: Record<string, SoundSpec>;
}

/** [foreground, background] colour tokens that must meet WCAG AA 4.5:1. */
export const REQUIRED_PAIRS: ReadonlyArray<
  readonly [keyof ThemeColours, keyof ThemeColours]
> = [
  ["text", "bg"],
  ["text", "panel"],
  ["textMuted", "bg"],
  ["textMuted", "panel"],
  ["accent", "bg"],
  ["cite", "bg"],
  ["cite", "panel"],
  ["danger", "bg"],
  ["danger", "panel"],
];

export const MIN_CONTRAST_RATIO = 4.5;
