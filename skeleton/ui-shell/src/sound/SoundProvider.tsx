import { useCallback, useMemo, useRef, useState, type ReactNode } from "react";
import type { SoundSpec } from "../theme/types";
import { SoundContext, type SoundApi } from "./useSound";

export interface SoundProviderProps {
  /** Typically the active theme's `sounds`. */
  sounds?: Record<string, SoundSpec>;
  children: ReactNode;
}

export function SoundProvider({ sounds, children }: SoundProviderProps) {
  const [muted, setMutedState] = useState(true);
  const mutedRef = useRef(true);
  const ctxRef = useRef<AudioContext | null>(null);
  const registered = useRef<Record<string, SoundSpec>>({});
  const themeSounds = useRef(sounds);
  themeSounds.current = sounds;

  const setMuted = useCallback((next: boolean) => {
    if (!next && !ctxRef.current && typeof AudioContext !== "undefined") {
      ctxRef.current = new AudioContext();
    }
    void ctxRef.current?.resume?.();
    mutedRef.current = next;
    setMutedState(next);
  }, []);

  const register = useCallback((name: string, spec: SoundSpec) => {
    registered.current[name] = spec;
  }, []);

  const play = useCallback((name: string) => {
    if (mutedRef.current) return;
    const spec = registered.current[name] ?? themeSounds.current?.[name];
    if (!spec) return;
    if (spec.kind === "url") {
      if (typeof Audio !== "undefined") void new Audio(spec.src).play?.();
      return;
    }
    const ctx = ctxRef.current;
    if (!ctx) return;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = spec.wave;
    osc.frequency.value = spec.freq;
    gain.gain.value = 0.1;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + spec.ms / 1000);
  }, []);

  const value = useMemo<SoundApi>(
    () => ({ play, muted, setMuted, register }),
    [play, muted, setMuted, register],
  );
  return <SoundContext.Provider value={value}>{children}</SoundContext.Provider>;
}
