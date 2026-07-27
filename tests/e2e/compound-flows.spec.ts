/**
 * Compound PLATE ceremony flows (offline).
 *
 * Proves multi-step chains the unit suite only covers in isolation (#927 / #364 residual):
 *   babysit merge gates (block → unblock)
 *   release cut dry-run + finalize/sync plan shape
 *   Q&A contemplate → artifact mutation PR-only draft plan
 *
 * Host-independent: no browser, no live GitHub, no secrets.
 * Driver: fixtures/compound_flow_driver.py
 */

import { test, expect } from "@playwright/test";
import { spawnSync } from "child_process";
import { join } from "path";

const WORKSPACE = process.env.WORKSPACE ?? join(__dirname, "..", "..");
const DRIVER = join(__dirname, "fixtures", "compound_flow_driver.py");
const PYTHON = process.platform === "win32" ? "python" : "python3";

function runCompoundDriver(): {
  ok: boolean;
  claims: string[];
  results: Record<string, unknown>;
  error?: string;
  proves?: string;
} {
  const result = spawnSync(PYTHON, [DRIVER], {
    encoding: "utf-8",
    env: {
      ...process.env,
      PYTHONPATH: [process.env.PYTHONPATH, join(WORKSPACE, "src")]
        .filter(Boolean)
        .join(process.platform === "win32" ? ";" : ":"),
    },
  });
  if (result.status !== 0 && !(result.stdout || "").trim()) {
    throw new Error(
      `compound_flow_driver exited ${result.status}: ${result.stderr || result.stdout}`
    );
  }
  const stdout = (result.stdout || "").trim();
  const start = stdout.search(/[{]/);
  if (start < 0) {
    throw new Error(
      `compound_flow_driver produced no JSON: status=${result.status} stderr=${result.stderr} stdout=${stdout}`
    );
  }
  return JSON.parse(stdout.slice(start));
}

test.describe("Compound PLATE flows (offline)", () => {
  test("driver proves babysit gates, release cut dry-run, and contemplation mutation plan", () => {
    const report = runCompoundDriver();
    expect(report.ok, report.error || "driver failed").toBe(true);
    expect(report.claims).toEqual(
      expect.arrayContaining([
        "babysit_gates_block_when_behind_threads_or_ci_fail",
        "babysit_gates_unblock_when_clean_approved_ci_green",
        "release_cut_dry_run_aggregates_fragments_without_write",
        "release_finalize_sync_plan_is_structured_dry_surface",
        "contemplate_detects_process_mutation_intents_pr_only",
        "contemplate_opens_feature_mutation_plan_with_release_base_draft",
      ])
    );
    expect(report.claims.length).toBeGreaterThanOrEqual(6);
    expect(report.proves).toContain("#927");
  });

  test("babysit results include blocked and clean evaluations", () => {
    const report = runCompoundDriver();
    expect(report.ok).toBe(true);
    const babysit = report.results.babysit as {
      blocked: { blocked: boolean };
      clean: { blocked: boolean };
    };
    expect(babysit.blocked.blocked).toBe(true);
    expect(babysit.clean.blocked).toBe(false);
  });

  test("release cut dry-run reports success and sync plan keys", () => {
    const report = runCompoundDriver();
    expect(report.ok).toBe(true);
    const release = report.results.release as {
      cut_exit: number;
      cut_stdout_has_dry_run: boolean;
      sync_plan_keys: string[];
    };
    expect(release.cut_exit).toBe(0);
    expect(release.cut_stdout_has_dry_run).toBe(true);
    expect(Array.isArray(release.sync_plan_keys)).toBe(true);
  });

  test("contemplate mutation plan includes AGENTS.md and Feature type", () => {
    const report = runCompoundDriver();
    expect(report.ok).toBe(true);
    const contemplate = report.results.contemplate as {
      paths: string[];
      created_types: string[];
      has_pr_draft: boolean;
    };
    expect(contemplate.paths).toContain("AGENTS.md");
    expect(contemplate.created_types).toContain("Feature");
    expect(contemplate.has_pr_draft).toBe(true);
  });
});
