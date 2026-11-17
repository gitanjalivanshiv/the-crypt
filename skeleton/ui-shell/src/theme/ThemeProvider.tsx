import { createContext, useContext, type CSSProperties, type ReactNode } from "react";
import type { Theme } from "./types";

const ThemeContext = createContext<Theme | null>(null);

/** Converts a theme into `--crypt-*` custom properties. */
export function themeToCssVars(theme: Theme): Record<string, string> {
  const vars: Record<string, string> = {
    "--crypt-font-family": theme.font.family,
    "--crypt-font-size-base": theme.font.sizeBase,
  };
  for (const [key, value] of Object.entries(theme.colours)) {
    vars[`--crypt-colour-${key.replace(/[A-Z]/g, (c) => `-${c.toLowerCase()}`)}`] = value;
  }
  for (const [key, value] of Object.entries(theme.effects)) {
    vars[`--crypt-effect-${key}`] = String(value);
  }
  return vars;
}

export interface ThemeProviderProps {
  theme: Theme;
  children?: ReactNode;
}

/** Writes theme tokens to custom properties on a wrapper element. */
export function ThemeProvider({ theme, children }: ThemeProviderProps) {
  return (
    <ThemeContext.Provider value={theme}>
      <div data-crypt-theme-root style={themeToCssVars(theme) as CSSProperties}>
        {children}
      </div>
    </ThemeContext.Provider>
  );
}

/** Returns the active theme. Components read tokens, never `theme.id`. */
export function useTheme(): Theme {
  const theme = useContext(ThemeContext);
  if (!theme) throw new Error("useTheme must be used within a ThemeProvider");
  return theme;
}
