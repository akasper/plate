/**
 * Copilot CLI plugin install / uninstall verification.
 *
 * These tests require the `copilot` binary to be on PATH (installed by CI or
 * the developer). They verify that the plugin can be installed from the local
 * workspace and cleanly removed — the minimum bar for "discovery works through
 * the Copilot CLI plugin".
 *
 * Tests are skipped when the `copilot` binary is not available so that
 * developers without the CLI can still run the rest of the suite locally.
 */

import { test, expect } from "@playwright/test";
import { spawnSync } from "child_process";
import { join } from "path";

const WORKSPACE = process.env.WORKSPACE ?? join(__dirname, "..", "..");

function copilotAvailable(): boolean {
  const result = spawnSync("copilot", ["--version"], { encoding: "utf-8" });
  return result.status === 0;
}

function runCopilot(...args: string[]): { status: number | null; stdout: string; stderr: string } {
  const result = spawnSync("copilot", args, {
    encoding: "utf-8",
    env: process.env,
  });
  return {
    status: result.status,
    stdout: result.stdout ?? "",
    stderr: result.stderr ?? "",
  };
}

test.describe("Copilot plugin install / uninstall", () => {
  test.beforeEach(({}, testInfo) => {
    if (!copilotAvailable()) {
      testInfo.skip();
    }
  });

  test.afterEach(() => {
    // Best-effort cleanup so tests remain idempotent.
    runCopilot("plugin", "uninstall", "plate-core");
  });

  test("plugin installs from local workspace path", () => {
    const result = runCopilot("plugin", "install", WORKSPACE);
    expect(
      result.status,
      `copilot plugin install failed:\n${result.stderr}`
    ).toBe(0);
  });

  test("plugin uninstalls cleanly after install", () => {
    // Ensure installed before testing uninstall.
    runCopilot("plugin", "install", WORKSPACE);

    const result = runCopilot("plugin", "uninstall", "plate-core");
    expect(
      result.status,
      `copilot plugin uninstall failed:\n${result.stderr}`
    ).toBe(0);
  });

  test("plugin install is idempotent (reinstall after install succeeds)", () => {
    runCopilot("plugin", "install", WORKSPACE);
    const result = runCopilot("plugin", "install", WORKSPACE);
    expect(
      result.status,
      `Second copilot plugin install failed:\n${result.stderr}`
    ).toBe(0);
  });
});
