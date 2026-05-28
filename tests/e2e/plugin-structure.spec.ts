/**
 * Plugin structure verification.
 *
 * These tests inspect the declarative plugin manifests and agent files on disk,
 * confirming that the Copilot CLI plugin has the expected structure before any
 * CLI tool is invoked.
 */

import { test, expect } from "@playwright/test";
import { readFileSync, existsSync } from "fs";
import { join } from "path";

// WORKSPACE is set in CI; fall back to the project root when running locally.
const WORKSPACE = process.env.WORKSPACE ?? join(__dirname, "..", "..");
const PLUGIN_ROOT = join(WORKSPACE, ".plugin");

test.describe("Copilot plugin structure", () => {
  test("plugin.json exists in the .plugin directory", () => {
    expect(existsSync(join(PLUGIN_ROOT, "plugin.json"))).toBe(true);
  });

  test("plugin.json contains required manifest fields", () => {
    const raw = readFileSync(join(PLUGIN_ROOT, "plugin.json"), "utf-8");
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    expect(manifest.name).toBe("plate-core");
    expect(typeof manifest.version).toBe("string");
    expect(manifest.agents).toBeTruthy();
    expect(manifest.mcpServers).toBeTruthy();
  });

  test("plate.agent.md exists inside the agents directory", () => {
    expect(existsSync(join(PLUGIN_ROOT, "agents", "plate.agent.md"))).toBe(
      true
    );
  });

  test("plate.agent.md references the required MCP tools", () => {
    const content = readFileSync(
      join(PLUGIN_ROOT, "agents", "plate.agent.md"),
      "utf-8"
    );
    expect(content).toContain("plate_health");
    expect(content).toContain("plate_epic_status");
    expect(content).toContain("plate_delegate_to_agent");
  });

  test("plate.agent.md includes baseline catalog guidance", () => {
    const content = readFileSync(
      join(PLUGIN_ROOT, "agents", "plate.agent.md"),
      "utf-8"
    );
    // The agent must mention the catalog surface commands so users can discover agents/skills.
    expect(content).toContain("gh plate agents");
    expect(content).toContain("gh plate skills");
  });

  test(".mcp.json wires up the plate-core MCP server", () => {
    const raw = readFileSync(join(PLUGIN_ROOT, ".mcp.json"), "utf-8");
    const config = JSON.parse(raw) as Record<string, unknown>;
    expect(config["plate-core"]).toBeTruthy();
  });
});
