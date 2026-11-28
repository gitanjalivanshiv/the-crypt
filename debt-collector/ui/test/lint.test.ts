import { readdirSync, readFileSync, statSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const REPO = join(here, "..", "..", "..");
const SHELL_SRC = join(REPO, "skeleton", "ui-shell", "src");
const APP_SRC = join(REPO, "debt-collector", "ui", "src");

const SOURCE = /\.(ts|tsx|js|jsx|css)$/;
const TEST_FILE = /\.(test|spec)\.[tj]sx?$/;

function walk(dir: string): string[] {
  const out: string[] = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (SOURCE.test(name) && !TEST_FILE.test(name)) out.push(p);
  }
  return out;
}

/** Drop comments so prose such as "never `theme.id`" is not a violation. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[\s;,{}(])\/\/.*$/gm, "$1");
}

function scan(files: string[], patterns: RegExp[]): string[] {
  const hits: string[] = [];
  for (const f of files) {
    const text = stripComments(readFileSync(f, "utf8"));
    text.split("\n").forEach((line, i) => {
      for (const re of patterns) {
        if (re.test(line)) hits.push(`${relative(REPO, f)}:${i + 1}: ${line.trim()}`);
      }
    });
  }
  return hits;
}

const THEME_NAMES = "ledger|phosphor";
const THEME_BRANCH: RegExp[] = [
  /\btheme\.id\b/,
  new RegExp(`[!=]==?\\s*["'\`](${THEME_NAMES})["'\`]`),
  new RegExp(`["'\`](${THEME_NAMES})["'\`]\\s*[!=]==?`),
  new RegExp(`\\bcase\\s+["'\`](${THEME_NAMES})["'\`]\\s*:`),
];

describe("source lint", () => {
  const shellFiles = walk(SHELL_SRC);
  const appFiles = walk(APP_SRC);

  it("finds the source trees it is meant to scan", () => {
    expect(shellFiles.length).toBeGreaterThan(0);
    expect(appFiles.length).toBeGreaterThan(0);
  });

  it("no code branches on theme.id or a theme name", () => {
    expect(scan([...shellFiles, ...appFiles], THEME_BRANCH)).toEqual([]);
  });

  it("the app does not redeclare shell components", () => {
    const decl = /\b(function|const|let|var|class)\s+(CrtFrame|ChatPanel|Meter)\b/;
    expect(scan(appFiles, [decl])).toEqual([]);
  });

  it("the app does not import from medium", () => {
    const imp: RegExp[] = [
      /\bfrom\s+["'][^"']*(^|\/)medium(\/[^"']*)?["']/,
      /\brequire\(\s*["'][^"']*(^|\/)medium(\/[^"']*)?["']\s*\)/,
      /\bimport\(\s*["'][^"']*(^|\/)medium(\/[^"']*)?["']\s*\)/,
    ];
    expect(scan(appFiles, imp)).toEqual([]);
  });

  it("the scanner detects planted violations", () => {
    const planted = ['if (theme.id === "x") {}', 'if (name == "ledger") {}'];
    for (const line of planted) {
      expect(THEME_BRANCH.some((re) => re.test(line))).toBe(true);
    }
  });
});
