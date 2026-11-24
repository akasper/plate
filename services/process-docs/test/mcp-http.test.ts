import { describe, expect, it } from "vitest";
import { handleMcpRequest, LATEST_PROTOCOL_VERSION } from "../src/mcp";
import type { Env } from "../src/env";
import { acceptsMcpMediaTypes } from "../src/accept";

const fixtureEnv: Env = {
  RELEASE_TAG: "v0.12.0-fixture",
  DOC_SOURCE: "fixture",
};

async function post(body: unknown, headers: Record<string, string> = {}) {
  const req = new Request("http://localhost/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json", ...headers },
    body: JSON.stringify(body),
  });
  return handleMcpRequest(req, fixtureEnv);
}

describe("accept header", () => {
  it("rejects q=0", () => {
    expect(acceptsMcpMediaTypes("application/json;q=0, text/event-stream;q=0")).toBe(false);
    expect(acceptsMcpMediaTypes("application/json;q=1")).toBe(true);
  });
});

describe("mcp http", () => {
  it("tools/list via JSON-RPC", async () => {
    const res = await post({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} });
    const json = (await res.json()) as { result: { tools: { name: string }[] } };
    const names = json.result.tools.map((t) => t.name);
    expect(names).toEqual(["list_docs", "get_doc", "search_docs"]);
  });

  it("initialize negotiates supported protocol", async () => {
    const res = await post({
      jsonrpc: "2.0",
      id: 3,
      method: "initialize",
      params: { protocolVersion: "2025-06-18", capabilities: {}, clientInfo: { name: "test", version: "0" } },
    });
    const json = (await res.json()) as { result: { protocolVersion: string } };
    expect(json.result.protocolVersion).toBe("2025-06-18");
  });

  it("initialize falls back to latest supported", async () => {
    const res = await post({
      jsonrpc: "2.0",
      id: 5,
      method: "initialize",
      params: { protocolVersion: "2099-01-01", capabilities: {}, clientInfo: { name: "test", version: "0" } },
    });
    const json = (await res.json()) as { result: { protocolVersion: string } };
    expect(json.result.protocolVersion).toBe(LATEST_PROTOCOL_VERSION);
  });

  it("empty batch returns -32600", async () => {
    const res = await post([]);
    expect(res.status).toBe(400);
    const json = (await res.json()) as { error: { code: number } };
    expect(json.error.code).toBe(-32600);
  });

  it("invalid batch element returns -32600", async () => {
    const res = await post([1, { jsonrpc: "2.0", id: 9, method: "tools/list", params: {} }]);
    const json = (await res.json()) as { error?: { code: number }; length?: number }[];
    expect(Array.isArray(json)).toBe(true);
    expect(json[0].error?.code).toBe(-32600);
    expect(json[1].result).toBeDefined();
  });

  it("zod failure returns -32602", async () => {
    const res = await post({
      jsonrpc: "2.0",
      id: 6,
      method: "tools/call",
      params: { name: "get_doc", arguments: {} },
    });
    const json = (await res.json()) as { error: { code: number } };
    expect(json.error.code).toBe(-32602);
  });

  it("notification without id yields 202 empty", async () => {
    const res = await post({ jsonrpc: "2.0", method: "notifications/initialized", params: {} });
    expect(res.status).toBe(202);
    expect(await res.text()).toBe("");
  });

  it("notification with id returns result object", async () => {
    const res = await post({ jsonrpc: "2.0", id: 7, method: "notifications/initialized", params: {} });
    const json = (await res.json()) as { result: Record<string, unknown> };
    expect(json.result).toEqual({});
  });

  it("tools/call get_doc", async () => {
    const res = await post({
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: "get_doc", arguments: { path: "wiki/Home.md", version: "latest" } },
    });
    const json = (await res.json()) as { result: { structuredContent: { content: string }; isError: boolean } };
    expect(json.result.structuredContent.content).toContain("fixture");
    expect(json.result.isError).toBe(false);
  });

  it("tools/call surfaces isError on failures", async () => {
    const res = await post({
      jsonrpc: "2.0",
      id: 4,
      method: "tools/call",
      params: { name: "get_doc", arguments: { path: "nope.md" } },
    });
    const json = (await res.json()) as { result: { isError: boolean } };
    expect(json.result.isError).toBe(true);
  });

  it("rejects Accept with q=0", async () => {
    const req = new Request("http://localhost/mcp", {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json;q=0" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: "tools/list", params: {} }),
    });
    const res = await handleMcpRequest(req, fixtureEnv);
    expect(res.status).toBe(400);
  });
});