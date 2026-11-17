import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SoundProvider } from "../src/sound/SoundProvider";
import { useSound } from "../src/sound/useSound";
import type { SoundSpec } from "../src/theme/types";

// Validates: Requirements 6.8
const created = vi.fn();
const started = vi.fn();

class MockAudioContext {
  currentTime = 0;
  destination = {};
  constructor() {
    created();
  }
  resume() {
    return Promise.resolve();
  }
  createGain() {
    return { gain: { value: 0 }, connect: vi.fn() };
  }
  createOscillator() {
    return {
      type: "",
      frequency: { value: 0 },
      connect: vi.fn(),
      start: started,
      stop: vi.fn(),
    };
  }
}

const themeSounds: Record<string, SoundSpec> = {
  cite: { kind: "tone", freq: 440, ms: 100, wave: "sine" },
};

function setup() {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SoundProvider sounds={themeSounds}>{children}</SoundProvider>
  );
  return renderHook(() => useSound(), { wrapper });
}

describe("sound hooks", () => {
  beforeEach(() => {
    created.mockClear();
    started.mockClear();
    vi.stubGlobal("AudioContext", MockAudioContext);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("starts muted, creates no context, and plays nothing while muted", () => {
    const { result } = setup();
    expect(result.current.muted).toBe(true);
    act(() => result.current.play("cite"));
    expect(created).not.toHaveBeenCalled();
    expect(started).not.toHaveBeenCalled();
  });

  it("creates the context on first unmute and plays theme sounds", () => {
    const { result } = setup();
    act(() => result.current.setMuted(false));
    expect(created).toHaveBeenCalledTimes(1);
    act(() => result.current.play("cite"));
    expect(started).toHaveBeenCalledTimes(1);
    act(() => result.current.setMuted(true));
    act(() => result.current.play("cite"));
    expect(started).toHaveBeenCalledTimes(1);
    act(() => result.current.setMuted(false));
    expect(created).toHaveBeenCalledTimes(1);
  });

  it("plays a registered sound", () => {
    const { result } = setup();
    act(() => result.current.setMuted(false));
    act(() => {
      result.current.register("banish", { kind: "tone", freq: 100, ms: 50, wave: "square" });
    });
    act(() => result.current.play("banish"));
    expect(started).toHaveBeenCalledTimes(1);
  });

  it("ignores unknown names", () => {
    const { result } = setup();
    act(() => result.current.setMuted(false));
    expect(() => act(() => result.current.play("nope"))).not.toThrow();
    expect(started).not.toHaveBeenCalled();
  });
});
