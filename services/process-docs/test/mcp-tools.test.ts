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
    const out = await mcpListDocs(store, {});
    expect(out.kind).toBe("ok");
    if (out.kind === "ok") expect(out.value.docs.length).toBeGreaterThan(0);
  });

  it("get_doc", async () => {
    const out = await mcpGetDoc(store, { path: "agents/autopilot-doctrine.md" });
    expect(out.kind).toBe("ok");
    if (out.kind === "ok") expect(String(out.value.content)).toContain("Autopilot");
  });

  it("get_doc error outcome", async () => {
    const out = await mcpGetDoc(store, { path: "missing.md" });
    expect(out.kind).toBe("err");
    if (out.kind === "err") expect(out.code).toBe("not_found");
  });

  it("get_doc rejects traversal", async () => {
    const out = await mcpGetDoc(store, { path: "%2e%2e/research/README.md" });
    expect(out.kind).toBe("err");
  });

  it("get_doc __proto__ does not inherit", async () => {
    const out = await mcpGetDoc(store, { path: "__proto__" });
    expect(out.kind).toBe("err");
  });

  it("unknown version", async () => {
    const out = await mcpGetDoc(store, { path: "wiki/Home.md", version: "v9.9.9" });
    expect(out.kind).toBe("err");
    if (out.kind === "err") expect(out.code).toBe("unknown_version");
  });

  it("search_docs", async () => {
    const out = await mcpSearchDocs(store, { query: "fixture" });
    expect(out.kind).toBe("ok");
    if (out.kind === "ok") expect(out.value.results.length).toBeGreaterThan(0);
  });
});