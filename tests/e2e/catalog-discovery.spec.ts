/**
 * Baseline agent and skill catalog discovery.
 *
 * These tests invoke the `gh-plate` CLI to confirm that all 12 baseline agents
 * and their associated skills are discoverable as JSON — the same data the
 * Copilot plugin surfaces through `gh plate agents list` and `gh plate skills list`.
 */

import { test, expect } from "@playwright/test";
import { spawnSync } from "child_process";
import { join } from "path";

const WORKSPACE = process.env.WORKSPACE ?? join(__dirname, "..", "..");
const GH_PLATE = join(WORKSPACE, "gh-plate");

// Resolve python3 / python depending on the host OS.
const PYTHON =
  process.platform === "win32" ? "python" : "python3";

function runGhPlate(...args: string[]): unknown {
  const result = spawnSync(PYTHON, [GH_PLATE, ...args], {
    encoding: "utf-8",
    env: process.env,
  });
  if (result.status !== 0) {
    throw new Error(
      `gh-plate ${args.join(" ")} exited ${result.status}: ${result.stderr}`
    );
  }
  return JSON.parse(result.stdout);
}

const EXPECTED_AGENT_IDS = [
  "project-manager",
  "market-researcher",
  "designer",
  "user-experience-engineer",
  "user-interface-designer",
  "software-engineer",
  "ci-engineer",
  "wiki-editor",
  "dev-relations-expert",
  "devops-engineer",
  "accountant",
  "research-agent",
];

test.describe("Baseline agent discovery", () => {
  test("agents list returns exactly 12 agents", () => {
    const result = runGhPlate("agents", "list", "--json") as {
      agents: Array<{ id: string }>;
    };
    expect(result.agents).toHaveLength(12);
  });

  for (const agentId of EXPECTED_AGENT_IDS) {
    test(`agent "${agentId}" is individually discoverable`, () => {
      const result = runGhPlate("agents", "show", agentId, "--json") as {
        id: string;
        name: string;
        surfaces: string[];
      };
      expect(result.id).toBe(agentId);
      expect(typeof result.name).toBe("string");
      expect(result.name.length).toBeGreaterThan(0);
    });
  }

  test("every agent declares at least one primary skill", () => {
    const result = runGhPlate("agents", "list", "--json") as {
      agents: Array<{ id: string; primary_skill_ids: string[] }>;
    };
    for (const agent of result.agents) {
      expect(
        agent.primary_skill_ids.length,
        `agent "${agent.id}" has no primary skills`
      ).toBeGreaterThan(0);
    }
  });

  test("every agent is available on the copilot-plugin surface", () => {
    const result = runGhPlate("agents", "list", "--json") as {
      agents: Array<{ id: string; surfaces: string[] }>;
    };
    for (const agent of result.agents) {
      expect(
        agent.surfaces,
        `agent "${agent.id}" missing copilot-plugin surface`
      ).toContain("copilot-plugin");
    }
  });
});

test.describe("Baseline skill discovery", () => {
  test("skills list returns at least 18 skills", () => {
    const result = runGhPlate("skills", "list", "--json") as {
      skills: Array<{ id: string }>;
    };
    expect(result.skills.length).toBeGreaterThanOrEqual(18);
  });

  test("every skill has at least one owning agent", () => {
    const result = runGhPlate("skills", "list", "--json") as {
      skills: Array<{ id: string; owning_agent_ids: string[] }>;
    };
    for (const skill of result.skills) {
      expect(
        skill.owning_agent_ids.length,
        `skill "${skill.id}" has no owning agents`
      ).toBeGreaterThan(0);
    }
  });

  test("all skill references from agents resolve to real skills", () => {
    const agentsResult = runGhPlate("agents", "list", "--json") as {
      agents: Array<{ id: string; primary_skill_ids: string[] }>;
    };
    const skillsResult = runGhPlate("skills", "list", "--json") as {
      skills: Array<{ id: string }>;
    };
    const skillIds = new Set(skillsResult.skills.map((s) => s.id));
    for (const agent of agentsResult.agents) {
      for (const skillId of agent.primary_skill_ids) {
        expect(
          skillIds.has(skillId),
          `agent "${agent.id}" references unknown skill "${skillId}"`
        ).toBe(true);
      }
    }
  });
});
