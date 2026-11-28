/**
 * The shell ships its component styles as a separate stylesheet. ThemeProvider only sets
 * CSS variables; without the stylesheet nothing consumes them and the app renders as bare
 * HTML -- no bezel, no panels, no cite styling. This package has no main.tsx (it boots
 * from an inline module in index.html), so the import lives in App.tsx and is easy to lose.
 * It was in fact missing until the deploy pass caught it on the bare URL.
 */
import { readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

const SRC = resolve(process.cwd(), "src");
const SHELL_CSS = "@kiroween/ui-shell/dist/style.css";

function sources(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = join(dir, e.name);
    if (e.isDirectory()) return sources(p);
    return /\.tsx?$/.test(e.name) ? [p] : [];
  });
}

describe("shell stylesheet", () => {
  it("is imported exactly once somewhere under src", () => {
    const importing = sources(SRC).filter((f) => readFileSync(f, "utf8").includes(SHELL_CSS));
    expect(importing).toHaveLength(1);
  });
});
