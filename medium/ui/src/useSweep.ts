import { useReducedMotion } from "@kiroween/ui-shell";
import { useEffect, useState } from "react";

export const SWEEP_INTERVAL_MS = 1200;

/**
 * Steps through `citedFiles` in claim order on a timer and returns the file
 * the ghost is currently "possessing", or null when nothing is cited.
 *
 * With reduced motion it returns the first cited file and starts no timer.
 * `paused` (a user selection, R5.5) stops the timer without changing the result.
 * The sweep stops on the last file rather than looping.
 */
export function useSweep(
  citedFiles: readonly string[],
  paused = false,
  intervalMs = SWEEP_INTERVAL_MS,
): string | null {
  const reduced = useReducedMotion();
  const key = citedFiles.join("\n");
  const [pos, setPos] = useState<{ key: string; index: number }>({ key, index: 0 });
  // A new cited set restarts the sweep from the first file.
  const index = pos.key === key ? pos.index : 0;

  useEffect(() => {
    if (reduced || paused || citedFiles.length < 2) return;
    const id = setInterval(() => {
      setPos((p) => {
        const current = p.key === key ? p.index : 0;
        return { key, index: Math.min(current + 1, citedFiles.length - 1) };
      });
    }, intervalMs);
    return () => clearInterval(id);
    // citedFiles is represented by `key`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reduced, paused, key, intervalMs]);

  if (citedFiles.length === 0) return null;
  return reduced ? citedFiles[0]! : (citedFiles[index] ?? citedFiles[0]!);
}
