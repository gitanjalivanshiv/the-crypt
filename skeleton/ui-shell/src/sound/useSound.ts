import { createContext, useContext } from "react";
import type { SoundSpec } from "../theme/types";

export interface SoundApi {
  /** Plays a named sound. No-op while muted or when the name is unknown. */
  play: (name: string) => void;
  muted: boolean;
  /** Unmuting must be called from a user gesture; it creates the AudioContext. */
  setMuted: (muted: boolean) => void;
  register: (name: string, spec: SoundSpec) => void;
}

const noop: SoundApi = {
  play: () => {},
  muted: true,
  setMuted: () => {},
  register: () => {},
};

export const SoundContext = createContext<SoundApi>(noop);

export function useSound(): SoundApi {
  return useContext(SoundContext);
}
