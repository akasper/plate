import { defineConfig } from "@playwright/test";
import { join } from "path";

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.ts",
  timeout: 30_000,
  retries: 0,
  reporter: process.env.CI ? "github" : "list",
  projects: [
    {
      name: "cli",
      // No browser — tests drive CLI subprocesses directly.
      use: {},
    },
  ],
});
