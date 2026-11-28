/**
 * A judge follows the submission link with no query string. Before the default ref existed
 * they landed on `missing_ref: add ?ref=<snapshot id> to the URL`, which is a wasted first
 * impression on a deployed demo. See docs/DEPLOY-PLAN.md.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { refFromLocation } from "../src/App";

// vitest runs with cwd at the package root; `import.meta.url` is not a file URL here.
const patient = JSON.parse(
  readFileSync(resolve(process.cwd(), "../../demo/patient.json"), "utf8"),
) as { primary: { commit: string } };

describe("default snapshot ref", () => {
  it("is the pinned patient commit, not a copy that can drift", () => {
    expect(__DEFAULT_REF__).toBe(patient.primary.commit);
  });

  it("is used when the URL carries no usable ref", () => {
    expect(refFromLocation("")).toBe(__DEFAULT_REF__);
    expect(refFromLocation("?ref=")).toBe(__DEFAULT_REF__);
    expect(refFromLocation("?other=x")).toBe(__DEFAULT_REF__);
  });

  it("never overrides an explicit ref", () => {
    expect(refFromLocation("?ref=snap-9")).toBe("snap-9");
  });
});
