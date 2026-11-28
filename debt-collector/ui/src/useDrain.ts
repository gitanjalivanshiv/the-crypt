import { useEffect, useRef, useState } from "react";
import { useReducedMotion } from "@kiroween/ui-shell";

/** The readout counts down in this many steps, one every STEP_MS (about 0.4 s in all). */
export const DRAIN_STEPS = 10;
export const STEP_MS = 40;

/**
 * Displayed outstanding-interest readout. Counts from the current value to `target`
 * in fixed steps and ends exactly on `target`. A new target mid-drain restarts from
 * the value on screen. With reduced motion it returns `target` and starts no timer.
 * Pure arithmetic over ledger numbers.
 */
export function useDrain(target: number): number {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(target);
  const current = useRef(target);

  useEffect(() => {
    if (reduced || current.current === target) {
      current.current = target;
      setShown(target);
      return;
    }
    const from = current.current;
    let step = 0;
    const id = setInterval(() => {
      step += 1;
      const next = step >= DRAIN_STEPS ? target : from + ((target - from) * step) / DRAIN_STEPS;
      current.current = next;
      setShown(next);
      if (step >= DRAIN_STEPS) clearInterval(id);
    }, STEP_MS);
    return () => clearInterval(id);
  }, [target, reduced]);

  return reduced ? target : shown;
}
