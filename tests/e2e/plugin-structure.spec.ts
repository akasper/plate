/**
 * Plugin structure verification.
 *
 * These tests inspect the declarative plugin manifests and agent files on disk,
 * confirming that the plugin has the expected structure and is free of
 * CLI-vendor-specific language before any CLI tool is invoked.
 *
 * Part of the expanded multi-host verification harness (see tests/e2e/README.md).
 * These structure tests serve as the host-independent simulation/certification
 * for CLI-agnostic claims.
 */

import { test, expect } from "@playwright/test";
import { readFileSync, existsSync } from "fs";
import { join } from "path";

// WORKSPACE is set in CI; fall back to the project root when running locally.
const WORKSPACE = process.env.WORKSPACE ?? join(__dirname, "..", "..");
const PLUGIN_ROOT = join(WORKSPACE, ".plugin");

test.describe("Plugin structure", () => {
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
    expect(manifest.skills).toBe("skills/");
  });

  test("plugin.json repository points to akasper/plate", () => {
    const raw = readFileSync(join(PLUGIN_ROOT, "plugin.json"), "utf-8");
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    expect(manifest.repository).toBe("https://github.com/akasper/plate");
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

  test("plate.agent.md contains no CLI-vendor-specific language", () => {
    const content = readFileSync(
      join(PLUGIN_ROOT, "agents", "plate.agent.md"),
      "utf-8"
    );
    const vendorTerms = ["Copilot CLI", "Copilot TUI", "Copilot form", "native Copilot"];
    for (const term of vendorTerms) {
      expect(content, `agent.md must not reference "${term}"`).not.toContain(term);
    }
  });

  test("plugin.json description contains no CLI-vendor-specific language", () => {
    const raw = readFileSync(join(PLUGIN_ROOT, "plugin.json"), "utf-8");
    const manifest = JSON.parse(raw) as Record<string, unknown>;
    const description = String(manifest.description ?? "");
    const vendorTerms = ["Copilot CLI", "Copilot plugin", "Grok Build"];
    for (const term of vendorTerms) {
      expect(description, `plugin.json description must not reference "${term}"`).not.toContain(term);
    }
  });

  test(".mcp.json wires up the plate-core MCP server for Grok runtime", () => {
    const raw = readFileSync(join(PLUGIN_ROOT, ".mcp.json"), "utf-8");
    const config = JSON.parse(raw) as Record<string, unknown>;
    const servers = config.mcpServers as Record<string, Record<string, unknown>>;
    expect(servers).toBeTruthy();
    expect(servers["plate-core"]).toBeTruthy();
    expect(servers["plate-core"].command).toBe("plate-mcp");
  });

  test("skills directory contains generated SKILL.md payloads", () => {
    const skillsRoot = join(PLUGIN_ROOT, "skills");
    expect(existsSync(skillsRoot)).toBe(true);
    const entries = readFileSync(join(PLUGIN_ROOT, "SKILLS.md"), "utf-8");
    expect(entries).toContain("PLATE-GENERATED:BEGIN skills-surface");
    expect(existsSync(join(skillsRoot, "crud-projects", "SKILL.md"))).toBe(true);
  });
});
