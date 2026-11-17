// @vitest-environment node
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

const root = resolve(import.meta.dirname, "..");

async function lintSource(code: string): Promise<string[]> {
  const eslint = new ESLint({ cwd: root });
  const results = await eslint.lintText(code, {
    filePath: join(root, "src", "probe.ts"),
  });
  return (results[0]?.messages ?? []).map((m) => `${m.ruleId}: ${m.message}`);
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    return statSync(p).isDirectory() ? walk(p) : [p];
  });
}

describe("UI shell independence (R7.1, R6.15)", () => {
  it.each([
    'import x from "../../../medium/x";',
    'import x from "../../debt-collector/y";',
    'export { z } from "../medium/z";',
  ])("rejects %s", async (code) => {
    const messages = await lintSource(code);
    expect(messages.some((m) => m.startsWith("no-restricted-imports"))).toBe(true);
  });

  it("accepts ordinary imports", async () => {
    expect(await lintSource('import { a } from "./types";')).toEqual([]);
  });

  it("src/ contains no persona names or persona copy", () => {
    const forbidden = /\bmedium\b|debt[ -]?collector|third ghost|nothing here has been touched/i;
    const offenders = walk(join(root, "src"))
      .filter((f) => /\.(ts|tsx|css|json)$/.test(f))
      .filter((f) => forbidden.test(readFileSync(f, "utf8")));
    expect(offenders).toEqual([]);
  });
});
