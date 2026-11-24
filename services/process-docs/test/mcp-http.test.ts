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

  it("initialize negotiates streamable HTTP protocol", async () => {
    const req = new Request("http://localhost/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 3,
        method: "initialize",
        params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "0" } },
      }),
    });
    const res = await handleMcpRequest(req, fixtureEnv);
    const json = (await res.json()) as { result: { protocolVersion: string } };
    expect(json.result.protocolVersion).toBe("2025-06-18");
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
    expect(json.result.isError).toBeFalsy();
  });

  it("tools/call surfaces isError on failures", async () => {
    const req = new Request("http://localhost/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: 4,
        method: "tools/call",
        params: { name: "get_doc", arguments: { path: "nope.md" } },
      }),
    });
    const res = await handleMcpRequest(req, fixtureEnv);
    const json = (await res.json()) as { result: { isError: boolean } };
    expect(json.result.isError).toBe(true);
  });
});