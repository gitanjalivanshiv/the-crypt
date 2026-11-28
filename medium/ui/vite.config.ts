/// <reference types="vitest" />
import { readFileSync } from "node:fs";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = process.env.MEDIUM_API_URL ?? "http://127.0.0.1:8000";

/**
 * The deployed demo must work from a bare URL. A judge follows the submission link with no
 * query string, and before this they landed on `missing_ref`. A retained snapshot's ref IS
 * its commit sha (`Retention.retained_ref` returns the snapshot id), so the pinned
 * patient's commit is the ref to open on. Read from demo/patient.json rather than copied,
 * so the pinned snapshot has one source of truth.
 */
const patient = JSON.parse(
  readFileSync(new URL("../../demo/patient.json", import.meta.url), "utf8"),
) as { primary: { commit: string } };
const DEFAULT_REF = process.env.VITE_DEFAULT_REF ?? patient.primary.commit;

export default defineConfig({
  define: { __DEFAULT_REF__: JSON.stringify(DEFAULT_REF) },
  plugins: [react()],
  server: {
    proxy: {
      "/snapshots": API,
      "/medium": API,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
