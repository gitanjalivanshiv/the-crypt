/// <reference types="vite/client" />
import type { ReactNode } from "react";
import { useReducedMotion } from "../hooks/useReducedMotion";
import styles from "./CrtFrame.module.css";

export interface CrtFrameProps {
  children?: ReactNode;
  className?: string;
}

/**
 * Bezel, scanline overlay and flicker around its children. The overlay is the
 * `::after` pseudo-element in CSS, so it is not in the accessibility tree.
 * Reduced motion removes the animation classes; CSS also turns them off.
 */
export function CrtFrame({ children, className }: CrtFrameProps) {
  const reduced = useReducedMotion();
  const classes = [styles.frame, !reduced && styles.scanlinesMoving, !reduced && styles.flicker, className]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={classes} data-crt-frame data-reduced-motion={reduced ? "true" : "false"}>
      {children}
    </div>
  );
}
