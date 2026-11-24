import { describe, expect, it } from "vitest";
import { createDocStore } from "../src/doc-store";
import type { Env } from "../src/env";
import { mcpGetDoc, mcpListDocs, mcpSearchDocs } from "../src/mcp-tools";

const fixtureEnv: Env = {
  RELEASE_TAG: "v0.12.0-fixture",
  DOC_SOURCE: "fixture",
};

describe("mcp tools", () => {
  const store = createDocStore(fixtureEnv);

  it("list_docs", async () => {
    const out = (await mcpListDocs(store, {})) as { docs: { path: string }[] };
    expect(out.docs.length).toBeGreaterThan(0);
  });

  it("get_doc", async () => {
    const out = (await mcpGetDoc(store, { path: "agents/autopilot-doctrine.md" })) as {
      content: string;
    };
    expect(out.content).toContain("Autopilot");
  });

  it("get_doc error shape", async () => {
    const out = (await mcpGetDoc(store, { path: "missing.md" })) as { error: string; code: string };
    expect(out.error).toBeTruthy();
    expect(out.code).toBe("not_found");
  });

  it("search_docs", async () => {
    const out = (await mcpSearchDocs(store, { query: "fixture" })) as {
      results: { path: string }[];
    };
    expect(out.results.length).toBeGreaterThan(0);
  });
});