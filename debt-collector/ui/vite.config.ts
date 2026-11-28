/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = process.env.COLLECTOR_API ?? "http://127.0.0.1:8001";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/snapshots": API,
      "/collector": API,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
