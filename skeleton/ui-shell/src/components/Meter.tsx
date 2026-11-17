/// <reference types="vite/client" />
import type { CSSProperties } from "react";
import { useReducedMotion } from "../hooks/useReducedMotion";
import styles from "./Meter.module.css";

export interface MeterProps {
  /** Fraction from 0 to 1. Values outside the range are clamped. */
  value: number;
  label: string;
  className?: string;
}

function clamp01(v: number): number {
  if (!Number.isFinite(v)) return 0;
  return Math.min(1, Math.max(0, v));
}

/**
 * Generic meter. It does not know what it measures; the caller supplies the
 * label. The fill animates between values unless reduced motion is requested.
 */
export function Meter({ value, label, className }: MeterProps) {
  const reduced = useReducedMotion();
  const v = clamp01(value);
  const classes = [styles.meter, className].filter(Boolean).join(" ");
  const fillClasses = [styles.fill, !reduced && styles.animated].filter(Boolean).join(" ");
  return (
    <div
      className={classes}
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={1}
      aria-valuenow={v}
      data-reduced-motion={reduced ? "true" : "false"}
    >
      <div className={fillClasses} style={{ "--meter-fraction": String(v) } as CSSProperties} />
    </div>
  );
}
