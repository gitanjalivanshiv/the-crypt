import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  MIN_CONTRAST_RATIO,
  REQUIRED_PAIRS,
  contrastRatio,
  ledger,
  phosphor,
} from "@kiroween/ui-shell";
import { describe, expect, it } from "vitest";
import { seance } from "../src/theme/seance";

const here = dirname(fileURLToPath(import.meta.url));
const SCAN_ROOTS = [
  resolve(here, "../../../skeleton/ui-shell/src"),
  resolve(here, "../src"),
];

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(ts|tsx)$/.test(name)) out.push(p);
  }
  return out;
}

/** Remove block and line comments so prose mentioning the rule is not flagged. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");
}

const FORBIDDEN = [
  /\btheme\.id\b/,
  /\.id\s*[!=]==?\s*["'`](?:phosphor|ledger|seance)["'`]/,
  /["'`](?:phosphor|ledger|seance)["'`]\s*[!=]==?/,
];

describe("seance theme", () => {
  it("has id seance and differs from the shell themes", () => {
    expect(seance.id).toBe("seance");
    expect(seance.colours).not.toEqual(phosphor.colours);
    expect(seance.colours).not.toEqual(ledger.colours);
    expect(seance.colours.text).not.toBe(phosphor.colours.text);
    expect(seance.colours.text).not.toBe(ledger.colours.text);
  });

  it.each(REQUIRED_PAIRS.map((p) => [p[0], p[1]] as const))(
    "%s on %s meets the minimum contrast ratio",
    (fg, bg) => {
      expect(
        contrastRatio(seance.colours[fg], seance.colours[bg]),
      ).toBeGreaterThanOrEqual(MIN_CONTRAST_RATIO);
    },
  );

  it("keeps every effect within 0..1", () => {
    for (const v of Object.values(seance.effects)) {
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("declares no sounds yet", () => {
    expect(seance.sounds).toEqual({});
  });

  it("no source under the shell or medium UI branches on theme identity", () => {
    const files = SCAN_ROOTS.flatMap(walk);
    expect(files.length).toBeGreaterThan(0);
    const offenders = files.filter((f) => {
      const code = stripComments(readFileSync(f, "utf8"));
      return FORBIDDEN.some((re) => re.test(code));
    });
    expect(offenders).toEqual([]);
  });
});
