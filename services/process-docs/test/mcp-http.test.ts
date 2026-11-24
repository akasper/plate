import { describe, expect, it } from "vitest";
import { handleMcpRequest } from "../src/mcp";
import type { Env } from "../src/env";

const fixtureEnv: Env = {
  RELEASE_TAG: "v0.12.0-fixture",
  DOC_SOURCE: "fixture",
};

describe("mcp http", () => {
  it("tools/list via JSON-RPC", async () => {
    const req = new Request("http://localhost/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
    });
    const res = await handleMcpRequest(req, fixtureEnv);
    const json = (await res.json()) as { result: { tools: { name: string }[] } };
    const names = json.result.tools.map((t) => t.name);
    expect(names).toEqual(["list_docs", "get_doc", "search_docs"]);
  });

  it("tools/call get_doc", async () => {
    const req = new Request("http://localhost/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 2,
        method: "tools/call",
        params: { name: "get_doc", arguments: { path: "wiki/Home.md", version: "latest" } },
      }),
    });
    const res = await handleMcpRequest(req, fixtureEnv);
    const json = (await res.json()) as { result: { structuredContent: { content: string } } };
    expect(json.result.structuredContent.content).toContain("fixture");
  });
});